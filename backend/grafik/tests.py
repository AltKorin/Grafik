"""Grafik boundaries (PLAN.md §6): what another firm must NOT reach, what a role must NOT do,
which shifts must NOT be saved, which taps must NOT count twice, which records must NOT change."""

from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from core.domain_errors import DomainError

from . import clock, domain, schedule, team
from .models import ChangeRequest, ClockPoint, Department, Employee, Punch, Shift, Unavailability, Workplace

PASSWORD = "A-long-unusual-phrase-74!"
NOW = datetime(2026, 11, 2, 7, 0, tzinfo=dt_timezone.utc)  # Monday 8:00 in Warsaw


def at(minutes):
    return mock.patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=minutes))


class World:
    """Firm X: director, kitchen (manager + cook with a card), reception (receptionist), a kiosk-only
    cleaner; firm Y: a director. Every person with a login gets an APIClient."""

    def __init__(self):
        User = get_user_model()
        self.x = Workplace.objects.create(name="Bistro X")
        self.y = Workplace.objects.create(name="Hotel Y")
        self.kitchen = Department.objects.create(workplace=self.x, name="Kuchnia")
        self.reception = Department.objects.create(workplace=self.x, name="Recepcja")
        self.people, self.clients = {}, {}
        for key, firm, role, dept in (
            ("dx", self.x, "dyrektor", None), ("kk", self.x, "kierownik", self.kitchen), ("ku", self.x, "pracownik", self.kitchen),
            ("re", self.x, "pracownik", self.reception), ("dy", self.y, "dyrektor", None),
        ):
            user = User.objects.create_user(key, password=PASSWORD)
            self.people[key] = Employee.objects.create(workplace=firm, user=user, name=f"Osoba {key.upper()}", role=role, department=dept)
            client = APIClient()
            client.force_authenticate(user)
            self.clients[key] = client
        self.people["sp"] = Employee.objects.create(workplace=self.x, name="Sprzątaczka", department=self.reception, card_uid="04A2B3C4")
        self.people["ku"].card_uid = "0011223344"
        self.people["ku"].save()
        self.point = ClockPoint.objects.create(workplace=self.x, name="Wejście", tag_token="tag-x")
        self.kiosk = team.new_kiosk(self.people["dx"].user, self.x.id, self.point.id)["kiosk_path"].split("/")[-1]

    def user(self, key):
        return self.people[key].user

    def shift(self, key, day="2026-11-03", start="08:00", end="16:00", by="dx"):
        return schedule.create_shift(self.user(by), self.x.id, {"employee": str(self.people[key].id), "date": day, "start": start, "end": end})


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.w = World()
        self.p = self.w.people

    def api(self, key):
        return self.w.clients[key]

    def url(self, rest, firm=None):
        return f"/api/w/{(firm or self.w.x).id}/{rest}"

    def assertDomain(self, status, fn, *args):
        with self.assertRaises(DomainError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status, str(caught.exception))
        return str(caught.exception)


class IsolationTests(Base):
    def test_other_firm_answers_404_everywhere(self):
        y = self.api("dy")
        for path in ("week/", "employees/", "departments/", "today/", "report/", "points/", "requests/", "export/"):
            with self.subTest(path=path):
                self.assertEqual(y.get(self.url(path)).status_code, 404)
        shift = self.w.shift("ku")
        self.assertEqual(y.delete(self.url(f"shifts/{shift['id']}/")).status_code, 404)
        self.assertEqual(y.post(self.url("shifts/"), {"employee": str(self.p["ku"].id), "date": "2026-11-03", "start": "08:00", "end": "16:00"},
                                format="json").status_code, 404)
        # firm Y's director passing an X employee to his own firm's endpoint: not found either
        body = {"employee": str(self.p["ku"].id), "date": "2026-11-03", "start": "08:00", "end": "16:00"}
        self.assertEqual(y.post(self.url("shifts/", self.w.y), body, format="json").status_code, 404)

    def test_anonymous_gets_nothing(self):
        anon = APIClient()
        self.assertIn(anon.get(self.url("week/")).status_code, (401, 403))
        self.assertEqual(anon.get("/api/workplaces/").status_code, 403)

    def test_workplaces_list_only_own(self):
        names = [w["name"] for w in self.api("ku").get("/api/workplaces/").json()]
        self.assertEqual(names, ["Bistro X"])


class NewFirmTests(Base):
    body = {"firm": "Kawiarnia Z", "name": "Jan Nowak", "accept": True}

    def test_account_without_firm_founds_one_and_directs_it(self):
        lone = get_user_model().objects.create_user("bez-firmy", password=PASSWORD)
        client = APIClient()
        client.force_authenticate(lone)
        self.assertEqual(client.get("/api/workplaces/").json(), [])
        made = client.post("/api/workplaces/", self.body, format="json")
        self.assertEqual(made.status_code, 200, made.content)
        self.assertEqual((made.json()["name"], made.json()["role"]), ("Kawiarnia Z", "dyrektor"))
        self.assertEqual(client.get(f"/api/w/{made.json()['id']}/employees/").status_code, 200)
        self.assertTrue(lone.termsacceptance_set.exists())

    def test_second_firm_stays_separate_from_the_first(self):
        made = self.api("ku").post("/api/workplaces/", self.body, format="json").json()
        self.assertEqual(made["role"], "dyrektor")
        self.assertEqual(sorted(w["role"] for w in self.api("ku").get("/api/workplaces/").json()), ["dyrektor", "pracownik"])
        # directing the new firm gives nothing in the old one
        self.assertEqual(self.api("ku").get(self.url("export/")).status_code, 403)
        self.assertEqual(self.api("dx").get(f"/api/w/{made['id']}/week/").status_code, 404)

    def test_bad_inputs_found_nothing(self):
        before = Workplace.objects.count()
        for bad in ({**self.body, "accept": False}, {**self.body, "firm": "  "}, {**self.body, "name": ""},
                    {**self.body, "firm": 7}, {**self.body, "firm": "x" * 201}, ["lista"]):
            with self.subTest(bad=bad):
                self.assertEqual(self.api("ku").post("/api/workplaces/", bad, format="json").status_code, 400)
        self.assertEqual(APIClient().post("/api/workplaces/", self.body, format="json").status_code, 403)
        self.assertEqual(Workplace.objects.count(), before)

    @override_settings(MAX_FIRMS_PER_ACCOUNT=2)
    def test_limit_of_firms_per_account(self):
        self.assertEqual(self.api("dx").post("/api/workplaces/", self.body, format="json").status_code, 200)
        self.assertEqual(self.api("dx").post("/api/workplaces/", self.body, format="json").status_code, 409)


class RoleTests(Base):
    def test_manager_arranges_only_own_department(self):
        self.w.shift("ku", by="kk")
        self.assertDomain(404, self.w.shift, "re", "2026-11-03", "08:00", "16:00", "kk")  # not even visible
        message = self.assertDomain(403, self.w.shift, "kk", "2026-11-03", "08:00", "16:00", "ku")
        self.assertIn("kierownik", message)

    def test_staff_cannot_arrange_or_correct(self):
        self.assertDomain(403, self.w.shift, "ku", "2026-11-03", "08:00", "16:00", "ku")
        self.assertDomain(403, clock.manual_punch, self.w.user("ku"), self.w.x.id,
                          {"employee": str(self.p["ku"].id), "kind": "in", "at": "2026-11-02T07:00", "note": "x"})
        self.assertDomain(403, team.create_department, self.w.user("kk"), self.w.x.id, {"name": "Bar"})

    def test_staff_sees_own_department_only(self):
        self.w.shift("re")
        week = schedule.week(self.w.user("ku"), self.w.x.id, {"week": "2026-11-02"})
        self.assertEqual({p["name"] for p in week["people"]}, {"Osoba KK", "Osoba KU"})
        self.assertEqual(week["shifts"], [])
        self.assertEqual(self.api("ku").get(self.url(f"unavailability/?employee={self.p['re'].id}")).status_code, 404)

    def test_unavailability_own_or_by_manager(self):
        schedule.create_unavailability(self.w.user("ku"), self.w.x.id, {"date_from": "2026-11-10", "kind": "urlop"})
        schedule.create_unavailability(self.w.user("kk"), self.w.x.id, {"employee": str(self.p["ku"].id), "date_from": "2026-11-12"})
        self.assertDomain(404, schedule.create_unavailability, self.w.user("kk"), self.w.x.id,
                          {"employee": str(self.p["re"].id), "date_from": "2026-11-12"})
        self.assertDomain(403, schedule.create_unavailability, self.w.user("re"), self.w.x.id,
                          {"employee": str(self.p["sp"].id), "date_from": "2026-11-12"})

    def test_reports_show_only_managed_people_or_self(self):
        names = {p["name"] for p in clock.report(self.w.user("kk"), self.w.x.id, {"month": "2026-11"})["people"]}
        self.assertEqual(names, {"Osoba KK", "Osoba KU"})
        names = {p["name"] for p in clock.report(self.w.user("re"), self.w.x.id, {"month": "2026-11"})["people"]}
        self.assertEqual(names, {"Osoba RE"})
        self.assertDomain(404, clock.punches, self.w.user("re"), self.w.x.id, {"employee": str(self.p["ku"].id)})


class ShiftTests(Base):
    def test_unavailability_blocks_then_withdrawal_unblocks_and_history_keeps_proof(self):
        u = schedule.create_unavailability(self.w.user("ku"), self.w.x.id, {"date_from": "2026-11-03", "date_to": "2026-11-04", "kind": "l4"})
        message = self.assertDomain(409, self.w.shift, "ku")
        self.assertIn("L4", message)
        schedule.delete_unavailability(self.w.user("ku"), self.w.x.id, u["id"])
        self.w.shift("ku")
        self.assertEqual(Unavailability.history.filter(id=u["id"], history_type="-").count(), 1)
        self.assertEqual(Unavailability.history.filter(id=u["id"], history_type="+").get().kind, "l4")

    def test_reporting_unavailability_names_existing_shifts(self):
        self.w.shift("ku")
        result = schedule.create_unavailability(self.w.user("ku"), self.w.x.id, {"date_from": "2026-11-01", "date_to": "2026-11-05"})
        self.assertEqual([c["date"] for c in result["conflicts"]], ["2026-11-03"])

    def test_overlaps_including_overnight(self):
        self.w.shift("ku", "2026-11-03", "22:00", "06:00")
        self.assertDomain(409, self.w.shift, "ku", "2026-11-04", "05:00", "13:00")
        self.w.shift("ku", "2026-11-04", "06:00", "14:00")  # touching is fine
        self.assertDomain(409, self.w.shift, "ku", "2026-11-03", "21:00", "23:00")

    def test_bad_inputs(self):
        for fields in ({"start": "08:00", "end": "08:00"}, {"date": "3.11.2026"}, {"start": "25:00"}, {"end": ""}, {"date": None},
                       {"employee": "not-a-uuid"}, {"notes": "x" * 201}):
            with self.subTest(fields=fields):
                body = {"employee": str(self.p["ku"].id), "date": "2026-11-03", "start": "08:00", "end": "16:00", **fields}
                with self.assertRaises(DomainError):
                    schedule.create_shift(self.w.user("dx"), self.w.x.id, body)
        self.assertEqual(Shift.objects.count(), 0)

    def test_update_keeps_checks_and_copy_week_skips_conflicts(self):
        s = self.w.shift("ku", "2026-10-27")
        self.w.shift("ku", "2026-10-28")
        schedule.update_shift(self.w.user("kk"), self.w.x.id, s["id"], {"date": "2026-10-27", "start": "09:00", "end": "17:00"})
        schedule.create_unavailability(self.w.user("ku"), self.w.x.id, {"date_from": "2026-11-04"})
        result = schedule.copy_week(self.w.user("kk"), self.w.x.id, {"week": "2026-11-05"})
        self.assertEqual(result["copied"], 1)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(Shift.objects.get(date="2026-11-03").start_time.hour, 9)


class RequestTests(Base):
    def test_swap_is_applied_once(self):
        mine = self.w.shift("ku", "2026-11-03")
        theirs = self.w.shift("kk", "2026-11-04")
        with at(0):
            r = schedule.create_request(self.w.user("ku"), self.w.x.id, {"kind": "swap", "shift": mine["id"], "swap_shift": theirs["id"]})
            self.assertDomain(403, schedule.review_request, self.w.user("ku"), self.w.x.id, r["id"], {}, True)
            schedule.review_request(self.w.user("kk"), self.w.x.id, r["id"], {"note": "ok"}, True)
            self.assertDomain(409, schedule.review_request, self.w.user("kk"), self.w.x.id, r["id"], {}, True)
        self.assertEqual(Shift.objects.get(pk=mine["id"]).employee, self.p["kk"])
        self.assertEqual(Shift.objects.get(pk=theirs["id"]).employee, self.p["ku"])

    def test_modify_respects_unavailability_and_rolls_back(self):
        s = self.w.shift("ku", "2026-11-03")
        with at(0):
            r = schedule.create_request(self.w.user("ku"), self.w.x.id,
                                        {"kind": "modify", "shift": s["id"], "new_date": "2026-11-05", "new_start": "10:00", "new_end": "18:00"})
            schedule.create_unavailability(self.w.user("ku"), self.w.x.id, {"date_from": "2026-11-05"})
            self.assertDomain(409, schedule.review_request, self.w.user("dx"), self.w.x.id, r["id"], {}, True)
        self.assertEqual(ChangeRequest.objects.get(pk=r["id"]).status, "pending")
        self.assertEqual(str(Shift.objects.get(pk=s["id"]).date), "2026-11-03")

    def test_request_rules(self):
        s = self.w.shift("ku", "2026-11-03")
        with at(0):
            self.assertDomain(404, schedule.create_request, self.w.user("re"), self.w.x.id, {"kind": "cancel", "shift": s["id"]})
            self.assertDomain(400, schedule.create_request, self.w.user("kk"), self.w.x.id, {"kind": "cancel", "shift": s["id"]})
            self.assertDomain(400, schedule.create_request, self.w.user("ku"), self.w.x.id, {"kind": "add", "new_date": "2026-10-01",
                                                                                              "new_start": "08:00", "new_end": "12:00"})
            r = schedule.create_request(self.w.user("ku"), self.w.x.id, {"kind": "cancel", "shift": s["id"], "reason": "wesele"})
            self.assertDomain(403, schedule.withdraw_request, self.w.user("kk"), self.w.x.id, r["id"])
            schedule.withdraw_request(self.w.user("ku"), self.w.x.id, r["id"])
            self.assertDomain(409, schedule.review_request, self.w.user("kk"), self.w.x.id, r["id"], {}, True)
            r = schedule.create_request(self.w.user("ku"), self.w.x.id, {"kind": "cancel", "shift": s["id"]})
            schedule.review_request(self.w.user("kk"), self.w.x.id, r["id"], {}, True)
        self.assertFalse(Shift.objects.filter(pk=s["id"]).exists())


class TagTests(Base):
    def test_phone_tap_in_repeat_out(self):
        ku = self.api("ku")
        with at(0):
            first = ku.post("/api/nfc/tag-x/").json()
        with at(0.5):
            again = ku.post("/api/nfc/tag-x/").json()
        with at(480):
            out = ku.post("/api/nfc/tag-x/").json()
        self.assertEqual((first["kind"], again["kind"], again["repeated"], out["kind"]), ("in", "in", True, "out"))
        self.assertEqual(first["time"], "08:00")
        self.assertEqual(Punch.objects.filter(employee=self.p["ku"]).count(), 2)

    def test_tag_needs_a_login_of_this_firm(self):
        anon = APIClient()
        self.assertEqual(anon.get("/api/nfc/tag-x/").json()["signed_in"], False)
        self.assertEqual(anon.post("/api/nfc/tag-x/").status_code, 401)
        self.assertEqual(self.api("dy").post("/api/nfc/tag-x/").status_code, 403)
        self.assertEqual(self.api("ku").post("/api/nfc/nie-ma/").status_code, 404)
        self.assertFalse(Punch.objects.exists())

    def test_session_post_needs_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="ku", password=PASSWORD)
        self.assertEqual(client.post("/api/nfc/tag-x/").status_code, 403)

    def test_entry_without_exit_expires(self):
        with at(0):
            self.api("ku").post("/api/nfc/tag-x/")
        with at(60 * 20):  # 20 h later: a new entry, the old one is flagged
            self.assertEqual(self.api("ku").post("/api/nfc/tag-x/").json()["kind"], "in")

    def test_new_tag_link_retires_the_old_sticker(self):
        team.new_tag(self.w.user("dx"), self.w.x.id, self.w.point.id)
        self.assertEqual(self.api("ku").post("/api/nfc/tag-x/").status_code, 404)


class KioskTests(Base):
    def kiosk(self, card, secret=None):
        return APIClient().post(f"/api/kiosk/{secret or self.w.kiosk}/", {"card": card}, format="json")

    def test_card_formats_and_unknown_cards(self):
        with at(0):
            self.assertEqual(self.kiosk("04:a2:b3:c4").json()["name"], "Sprzątaczka")
            self.assertEqual(self.kiosk("deadbeef").status_code, 404)
        unknown = team.unknown_cards(self.w.user("dx"), self.w.x.id)
        self.assertEqual([c["uid"] for c in unknown], ["DEADBEEF"])
        team.assign_card(self.w.user("dx"), self.w.x.id, self.p["re"].id, {"uid": "DEADBEEF"})
        self.assertEqual(team.unknown_cards(self.w.user("dx"), self.w.x.id), [])
        self.assertDomain(409, team.assign_card, self.w.user("dx"), self.w.x.id, self.p["ku"].id, {"uid": "deadbeef"})
        for bad in ("", "  ", "ab", "ż" * 8, None, ["04A2"]):
            with self.subTest(bad=bad):
                self.assertEqual(self.kiosk(bad).status_code, 400)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache_table"}})
    def test_unknown_card_survives_the_rollback_with_the_database_cache(self):
        call_command("createcachetable", verbosity=0)  # production keeps the cache in the database
        self.assertEqual(self.kiosk("CAFEBABE").status_code, 404)
        self.assertEqual([c["uid"] for c in team.unknown_cards(self.w.user("dx"), self.w.x.id)], ["CAFEBABE"])

    def test_wrong_or_removed_kiosk_link(self):
        self.assertEqual(self.kiosk("04A2B3C4", "zly-sekret").status_code, 404)
        self.assertEqual(APIClient().get("/api/kiosk/tag-x/").status_code, 404)  # the public sticker token is not a kiosk
        team.remove_kiosk(self.w.user("dx"), self.w.x.id, self.w.point.id)
        self.assertEqual(self.kiosk("04A2B3C4").status_code, 404)
        self.assertFalse(Punch.objects.exists())

    def test_kiosk_works_on_a_logged_in_tablet_without_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="dx", password=PASSWORD)
        self.assertEqual(client.post(f"/api/kiosk/{self.w.kiosk}/", {"card": "04A2B3C4"}, format="json").status_code, 200)

    def test_archived_person_card_stops(self):
        with at(0):
            self.kiosk("04A2B3C4")
        team.delete_employee(self.w.user("dx"), self.w.x.id, self.p["sp"].id)
        self.p["sp"].refresh_from_db()
        self.assertFalse(self.p["sp"].active)
        self.assertEqual(self.kiosk("04A2B3C4").status_code, 404)


class PunchRecordTests(Base):
    def test_punches_are_immutable_and_corrections_are_events(self):
        with at(0):
            p = Punch.objects.create(workplace=self.w.x, employee=self.p["ku"], kind="in", at=NOW, source="kiosk")
        with self.assertRaises(PermissionError):
            p.save()
        with self.assertRaises(PermissionError):
            p.delete()
        with at(600):
            self.assertDomain(400, clock.void_punch, self.w.user("kk"), self.w.x.id, p.pk, {"note": "  "})
            clock.void_punch(self.w.user("kk"), self.w.x.id, p.pk, {"note": "pomyłka"})
            self.assertDomain(409, clock.void_punch, self.w.user("kk"), self.w.x.id, p.pk, {"note": "znowu"})
            clock.manual_punch(self.w.user("kk"), self.w.x.id, {"employee": str(self.p["ku"].id), "kind": "in", "at": "2026-11-02T09:00", "note": "zapomniał"})
            clock.manual_punch(self.w.user("kk"), self.w.x.id, {"employee": str(self.p["ku"].id), "kind": "out", "at": "2026-11-02T15:30", "note": "zapomniał"})
            self.assertDomain(400, clock.manual_punch, self.w.user("kk"), self.w.x.id,
                              {"employee": str(self.p["ku"].id), "kind": "in", "at": "2026-12-01T09:00", "note": "przyszłość"})
            report = clock.report(self.w.user("kk"), self.w.x.id, {"month": "2026-11", "employee": str(self.p["ku"].id)})
        person = report["people"][0]
        self.assertEqual((person["worked"], person["problems"]), (390, 0))
        self.assertEqual(Punch.objects.count(), 4)  # nothing disappeared

    def test_report_and_csv(self):
        self.w.shift("ku", "2026-11-02", "08:00", "16:00")
        for minutes in (0, 485):
            with at(minutes):
                self.kiosk_tap()
        with at(600):
            month, body = clock.report_csv(self.w.user("dx"), self.w.x.id, {"month": "2026-11"})
            person = [p for p in clock.report(self.w.user("dx"), self.w.x.id, {"month": "2026-11"})["people"] if p["name"] == "Osoba KU"][0]
        self.assertEqual((person["planned"], person["worked"]), (480, 485))
        self.assertTrue(body.startswith("﻿"))
        self.assertIn("2026-11-02;Osoba KU;Kuchnia;08:00–16:00;8:00;08:00–16:05;8:05;", body)
        self.assertDomain(400, clock.report, self.w.user("dx"), self.w.x.id, {"month": "2026-13"})

    def kiosk_tap(self):
        return clock.kiosk_punch(self.w.kiosk, {"card": "0011223344"})


class TeamTests(Base):
    def test_accounts_cards_and_directors(self):
        created = team.create_employee(self.w.user("dx"), self.w.x.id, {"name": "Nowy", "department": str(self.w.kitchen.id), "login": "Nowy.K"})
        self.assertEqual(created["login"], "nowy.k")
        self.assertTrue(APIClient().login(username="nowy.k", password=created["password"]))
        self.assertDomain(409, team.create_employee, self.w.user("dx"), self.w.x.id, {"name": "Inny", "login": "NOWY.K"})
        self.assertDomain(409, team.update_employee, self.w.user("dx"), self.w.x.id, self.p["dx"].id, {"name": "D", "role": "pracownik"})
        self.assertDomain(409, team.delete_employee, self.w.user("dx"), self.w.x.id, self.p["dx"].id)
        self.assertDomain(400, team.create_employee, self.w.user("dx"), self.w.x.id, {"name": "Kier", "role": "kierownik"})
        self.assertDomain(400, team.create_employee, self.w.user("dx"), self.w.x.id, {"name": "   "})
        team.remove_account(self.w.user("dx"), self.w.x.id, created["id"])
        self.assertFalse(get_user_model().objects.get(username="nowy.k").is_active)

    def test_department_in_use_cannot_be_deleted(self):
        message = self.assertDomain(409, team.delete_department, self.w.user("dx"), self.w.x.id, self.w.kitchen.id)
        self.assertIn("Osoba KK", message)
        empty = team.create_department(self.w.user("dx"), self.w.x.id, {"name": "Bar", "color": "#aabbcc"})
        self.assertDomain(409, team.create_department, self.w.user("dx"), self.w.x.id, {"name": "Bar"})
        self.assertDomain(400, team.create_department, self.w.user("dx"), self.w.x.id, {"name": "Spa", "color": "red"})
        team.delete_department(self.w.user("dx"), self.w.x.id, empty["id"])

    def test_delete_firm_erases_it_and_spares_the_other(self):
        with at(0):
            clock.kiosk_punch(self.w.kiosk, {"card": "04A2B3C4"})
        self.w.shift("ku")
        schedule.create_unavailability(self.w.user("re"), self.w.x.id, {"date_from": "2026-11-20"})
        self.assertDomain(400, team.delete_workplace, self.w.user("dx"), self.w.x.id, {"confirm": "Bistro"})
        result = team.delete_workplace(self.w.user("dx"), self.w.x.id, {"confirm": " Bistro X "})
        self.assertTrue(result["account_removed"])
        self.assertFalse(Workplace.objects.filter(pk=self.w.x.id).exists())
        self.assertEqual(Punch.objects.count(), 0)
        x = self.w.x.id
        self.assertFalse(Workplace.history.filter(id=x).exists())
        for model in (Employee, Department, ClockPoint):
            self.assertFalse(model.history.filter(workplace_id=x).exists(), model)
        self.assertFalse(Shift.history.exists())
        self.assertFalse(Unavailability.history.exists())
        self.assertTrue(get_user_model().objects.get(pk=self.w.user("dx").pk).username.startswith("usuniety-"))
        self.assertTrue(Workplace.objects.filter(pk=self.w.y.id).exists())
        self.assertTrue(get_user_model().objects.get(username="dy").is_active)


class SessionMathTests(SimpleTestCase):
    def p(self, pk, kind, hour, voids=None):
        return SimpleNamespace(pk=pk, kind=kind, at=NOW + timedelta(hours=hour), voids_id=voids)

    def test_pairs_overnight_and_problems(self):
        punches = [self.p(1, "out", 0), self.p(2, "in", 1), self.p(3, "in", 2), self.p(4, "out", 10),
                   self.p(5, "in", 20), self.p(6, "out", 28)]
        result = domain.sessions(punches, NOW + timedelta(hours=30), 16)
        self.assertEqual([s["problem"] for s in result], ["wyjście bez wejścia", "brak wyjścia", None, None])
        self.assertEqual([domain.worked_minutes(s) for s in result], [0, 0, 480, 480])

    def test_void_and_ongoing(self):
        punches = [self.p(1, "in", 0), self.p(2, "out", 1), self.p(3, "void", 2, voids=2)]
        ongoing = domain.sessions(punches, NOW + timedelta(hours=3), 16)
        self.assertEqual(ongoing, [{"start": NOW, "end": None, "in": 1, "out": None, "problem": None}])
        stale = domain.sessions(punches, NOW + timedelta(hours=17), 16)
        self.assertEqual(stale[0]["problem"], "brak wyjścia")

    def test_shift_minutes_and_next_kind(self):
        from datetime import time

        self.assertEqual(domain.shift_minutes(time(22), time(6)), 480)
        self.assertEqual(domain.shift_minutes(time(8), time(16, 30)), 510)
        self.assertEqual(domain.next_kind(None, NOW, 16), "in")
        self.assertEqual(domain.next_kind(self.p(1, "in", -1), NOW, 16), "out")
        self.assertEqual(domain.next_kind(self.p(1, "in", -17), NOW, 16), "in")
        self.assertEqual(domain.next_kind(self.p(1, "out", -1), NOW, 16), "in")


class ManagerTeamTests(Base):
    """A department manager runs the accounts of his own department's employees — and nothing else."""

    def test_manager_adds_employee_only_to_own_department_as_employee(self):
        kk = self.api("kk")
        made = kk.post(self.url("employees/"), {"name": "Nowy Kucharz"}, format="json")
        self.assertEqual(made.status_code, 200, made.content)
        self.assertEqual((made.json()["role"], made.json()["department"]), ("pracownik", str(self.w.kitchen.id)))
        for bad in ({"name": "X", "role": "dyrektor"}, {"name": "X", "role": "kierownik", "department": str(self.w.kitchen.id)},
                    {"name": "X", "department": str(self.w.reception.id)}):
            with self.subTest(bad=bad):
                self.assertEqual(kk.post(self.url("employees/"), bad, format="json").status_code, 403)
        self.assertEqual(self.api("ku").post(self.url("employees/"), {"name": "X"}, format="json").status_code, 403)

    def test_manager_touches_only_his_employees(self):
        kk = self.api("kk")
        ku, re_, dx = (self.p[k].id for k in ("ku", "re", "dx"))
        self.assertEqual(kk.post(self.url(f"employees/{ku}/account/"), {"login": "kucharz.ku"}, format="json").status_code, 200)
        self.assertEqual(kk.post(self.url(f"employees/{re_}/account/"), {"login": "obca.osoba"}, format="json").status_code, 404)
        self.assertEqual(kk.post(self.url(f"employees/{dx}/invite/")).status_code, 404)  # director: no department
        self.assertEqual(kk.patch(self.url(f"employees/{ku}/"), {"name": "Ku", "role": "kierownik"}, format="json").status_code, 403)
        self.assertEqual(kk.delete(self.url(f"employees/{self.p['kk'].id}/"), {}, format="json").status_code, 403)  # himself: a manager
        self.assertEqual(kk.post(self.url("points/"), {"name": "X"}, format="json").status_code, 403)


class InvitationTests(Base):
    def invite(self, key="sp", by="dx"):
        r = self.api(by).post(self.url(f"employees/{self.p[key].id}/invite/"))
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["invite_path"].rsplit("/", 1)[1]

    def test_link_lets_the_employee_choose_login_and_password_once(self):
        made = self.api("kk").post(self.url("employees/"), {"name": "Żaneta Łącka"}, format="json").json()
        self.p["sp"] = Employee.objects.get(pk=made["id"])  # the manager's new cook, invited by the manager
        secret = self.invite(by="kk")
        guest = APIClient(enforce_csrf_checks=True)
        info = guest.get(f"/api/invite/{secret}/").json()
        self.assertEqual((info["name"], info["workplace"], info["login"]), ("Żaneta Łącka", "Bistro X", "zaneta.lacka"))
        self.assertEqual(guest.post(f"/api/invite/{secret}/", {"login": "ewa.s", "password": PASSWORD}, format="json").status_code, 403)  # no CSRF
        guest = APIClient()
        done = guest.post(f"/api/invite/{secret}/", {"login": "Ewa.S", "password": PASSWORD}, format="json")
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(guest.get("/api/session/").json()["user"], "ewa.s")  # signed in right away
        self.assertEqual(guest.get(self.url("today/")).status_code, 200)
        self.p["sp"].refresh_from_db()
        self.assertEqual((self.p["sp"].user.username, self.p["sp"].invite_hash), ("ewa.s", ""))
        self.assertEqual(APIClient().get(f"/api/invite/{secret}/").status_code, 404)  # one use
        self.assertEqual(self.api("dx").post(self.url(f"employees/{self.p['sp'].id}/invite/")).status_code, 409)

    def test_bad_links_and_inputs_create_nothing(self):
        secret = self.invite()
        guest = APIClient()
        users = get_user_model().objects.count()
        for bad in ({"login": "ewa", "password": "krotkie"}, {"login": "ż", "password": PASSWORD}, {"login": "ku", "password": PASSWORD},
                    {"login": "dx", "password": PASSWORD}, {"password": PASSWORD}, {"login": "ewa", "password": 7}, []):
            with self.subTest(bad=bad):
                self.assertIn(guest.post(f"/api/invite/{secret}/", bad, format="json").status_code, (400, 409))
        for wrong in ("x", "a" * 43, ""):
            self.assertEqual(guest.get(f"/api/invite/{wrong or '-'}/").status_code, 404)
        newer = self.invite()  # a new link retires the old one
        self.assertEqual(guest.get(f"/api/invite/{secret}/").status_code, 404)
        self.assertEqual(self.api("dx").delete(self.url(f"employees/{self.p['sp'].id}/invite/"), {}, format="json").status_code, 200)
        self.assertEqual(guest.get(f"/api/invite/{newer}/").status_code, 404)  # cancelled
        expiring = self.invite()
        with at(60 * 24 * 365):
            self.assertEqual(guest.get(f"/api/invite/{expiring}/").status_code, 404)
        self.assertEqual(get_user_model().objects.count(), users)

    def test_archived_or_foreign_people_get_no_invitation(self):
        self.p["sp"].active = False
        self.p["sp"].save()
        self.assertEqual(self.api("dx").post(self.url(f"employees/{self.p['sp'].id}/invite/")).status_code, 409)
        self.assertEqual(self.api("dy").post(self.url(f"employees/{self.p['ku'].id}/invite/")).status_code, 404)
        self.assertEqual(self.api("re").post(self.url(f"employees/{self.p['ku'].id}/invite/")).status_code, 403)


class SeedTests(TestCase):
    @override_settings(DEBUG=False)
    def test_demo_needs_its_own_password_on_a_server(self):
        from django.core.management.base import CommandError

        with mock.patch.dict("os.environ", {"DEMO_PASSWORD": ""}), self.assertRaises(CommandError):
            call_command("seed_demo")
        self.assertFalse(Workplace.objects.exists())


@override_settings(DEMO_MAX=3, DEMO_HOURS=24)
class SandboxDemoTests(TestCase):
    """„Wypróbuj demo”: every visitor gets an own firm, can look as any role, and it all disappears."""

    def setUp(self):
        cache.clear()  # the per-IP limit on new demos would carry over between tests

    def visitor(self):
        client = APIClient()
        started = client.post("/api/demo/", format="json")
        self.assertEqual(started.status_code, 200, started.content)
        return client, started.json()["demo"]

    def test_visitor_gets_own_firm_as_director_and_can_switch_roles(self):
        a, demo_a = self.visitor()
        b, demo_b = self.visitor()
        self.assertNotEqual(demo_a["workplace"], demo_b["workplace"])
        self.assertEqual(demo_a["role"], "dyrektor")
        firm = demo_a["workplace"]
        self.assertEqual([w["id"] for w in a.get("/api/workplaces/").json()], [firm])
        self.assertEqual(a.get(f"/api/w/{firm}/points/").status_code, 200)
        self.assertEqual(b.get(f"/api/w/{firm}/week/").status_code, 404)  # the other visitor's firm
        self.assertEqual(a.post("/api/demo/as/", {"role": "pracownik"}, format="json").json()["demo"]["role"], "pracownik")
        self.assertEqual(a.get(f"/api/w/{firm}/points/").status_code, 403)  # now really an employee
        self.assertEqual(a.post(demo_a["tag"].replace("/nfc/", "/api/nfc/") + "/").json()["kind"], "in")  # the sticker works
        self.assertEqual(a.post("/api/demo/as/", {"role": "admin"}, format="json").status_code, 400)
        self.assertEqual(APIClient().post("/api/demo/as/", {"role": "dyrektor"}, format="json").status_code, 404)

    def test_demo_accounts_have_no_password_and_found_no_firms(self):
        client, demo = self.visitor()
        login = Employee.objects.get(workplace_id=demo["workplace"], role="dyrektor").user.username
        self.assertFalse(get_user_model().objects.get(username=login).has_usable_password())
        self.assertEqual(APIClient().post("/api/session/", {"username": login, "password": ""}, format="json").status_code, 400)
        self.assertEqual(client.post("/api/workplaces/", {"firm": "Prawdziwa", "name": "X", "accept": True}, format="json").status_code, 403)

    def test_limit_csrf_and_switch_off(self):
        for _ in range(3):
            self.visitor()
        self.assertEqual(APIClient().post("/api/demo/", format="json").status_code, 503)  # backpressure
        self.assertEqual(APIClient(enforce_csrf_checks=True).post("/api/demo/", format="json").status_code, 403)
        with override_settings(DEMO_MAX=0):
            self.assertEqual(APIClient().post("/api/demo/", format="json").status_code, 503)
            self.assertFalse(APIClient().get("/api/public-config/").json()["demo"])

    def test_expired_sandbox_disappears_with_its_accounts(self):
        client, demo = self.visitor()
        users = get_user_model().objects.count()
        with at(60 * 25):
            self.assertIsNone(client.get("/api/demo/").json()["demo"])
            fresh, _ = self.visitor()  # starting a new one sweeps the expired ones
        self.assertFalse(Workplace.objects.filter(pk=demo["workplace"]).exists())
        self.assertEqual(get_user_model().objects.count(), users)  # 5 gone, 5 new

    def test_superuser_does_not_see_sandboxes(self):
        self.visitor()
        real = Workplace.objects.create(name="Prawdziwa")
        admin = get_user_model().objects.create_superuser("szef", password=PASSWORD)
        client = APIClient()
        client.force_authenticate(admin)
        self.assertEqual([w["id"] for w in client.get("/api/workplaces/").json()], [str(real.id)])
