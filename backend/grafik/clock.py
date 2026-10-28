"""Czas pracy: punches from the NFC sticker (own phone) and the kiosk (card), managers' corrections,
who is at work now, and the monthly report — always recomputed from the punch events (PLAN.md §5)."""

import calendar
import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.domain_errors import DomainError
from core.i18n import tr

from . import domain, team
from .access import employee_in, manages, require_manager, sees, workplace_access
from .models import ClockPoint, Employee, Punch, Shift
from .schedule import hm, shift_json, visible_people


def last_effective(employee):
    return employee.punches.exclude(kind="void").filter(voided_by__isnull=True).order_by("-at", "-pk").first()


def local_hm(moment, tz):
    return moment.astimezone(tz).strftime("%H:%M")


def punch_result(p, repeated, tz):
    return {"name": p.employee.name, "kind": p.kind, "kind_label": tr(p.get_kind_display()), "at": p.at.isoformat(),
            "time": local_hm(p.at, tz), "repeated": repeated}


def record(employee, source, point):
    """One tap = one event. A second tap within PUNCH_DEBOUNCE_SECONDS answers the first one again
    (a phone reopening the page, a card held too long) instead of turning an entry into an exit."""
    Employee.objects.select_for_update().filter(pk=employee.pk).first()  # one tap at a time per person
    now = timezone.now()
    tz = domain.zone(employee.workplace.timezone)
    last = last_effective(employee)
    if last and last.source != "manual" and now - last.at < timedelta(seconds=settings.PUNCH_DEBOUNCE_SECONDS):
        return punch_result(last, True, tz)
    kind = domain.next_kind(last, now, settings.MAX_SHIFT_HOURS)
    p = Punch.objects.create(workplace=employee.workplace, employee=employee, kind=kind, at=now, source=source, point=point,
                             recorded_by=employee.user)
    return punch_result(p, False, tz)


# --- sticker: the person's own phone, logged in ----------------------------------------------

def tag_point(tag_token):
    p = ClockPoint.objects.select_related("workplace").filter(tag_token=tag_token).first() if isinstance(tag_token, str) else None
    if not p:
        raise DomainError("Ten punkt odbić nie istnieje — naklejka mogła zostać wymieniona", 404)
    return p


def tag_info(user, tag_token):
    p = tag_point(tag_token)
    me = Employee.objects.filter(workplace=p.workplace, user=user, active=True).first() if user.is_authenticated else None
    return {"point": p.name, "workplace": p.workplace.name, "signed_in": user.is_authenticated,
            "employee": me.name if me else None}


@transaction.atomic
def tag_punch(user, tag_token):
    p = tag_point(tag_token)
    if not user.is_authenticated:
        raise DomainError("Zaloguj się, żeby odbić", 401)
    me = Employee.objects.select_related("workplace").filter(workplace=p.workplace, user=user, active=True).first()
    if not me:
        raise DomainError("To konto nie należy do pracowników firmy {firm}", 403, firm=p.workplace.name)
    return record(me, "tag", p)


# --- kiosk: a tablet at the entrance, cards and key fobs ---------------------------------------

def kiosk_point(secret):
    p = ClockPoint.objects.select_related("workplace").filter(
        kiosk_hash=team.digest(secret)).first() if isinstance(secret, str) and secret else None
    if not p:
        raise DomainError("Kiosk: nie znaleziono — link mógł zostać wymieniony w panelu", 404)
    return p


def kiosk_info(secret):
    p = kiosk_point(secret)
    return {"point": p.name, "workplace": p.workplace.name, "timezone": p.workplace.timezone}


def kiosk_punch(secret, data):
    p = kiosk_point(secret)
    uid = team.normalize_card(domain.body_object(data).get("card"))
    e = Employee.objects.select_related("workplace").filter(workplace=p.workplace, card_uid=uid, active=True).first()
    if not e:
        # Outside any transaction: the cache lives in the database and the error would roll it back.
        team.remember_unknown_card(p.workplace, uid, p)
        raise DomainError("Nieznana karta — poproś kierownika o przypisanie jej w panelu", 404)
    with transaction.atomic():
        return record(e, "kiosk", p)


# --- managers' corrections (new events, never edits) --------------------------------------------

def local_moment(value, tz, label="czas"):
    try:
        if isinstance(value, str) and 16 <= len(value) <= 19:
            moment = datetime.fromisoformat(value)
            if moment.tzinfo is None:
                return moment.replace(tzinfo=tz, second=0, microsecond=0)
    except ValueError:
        pass
    raise DomainError("Pole „{label}”: data i godzina w formacie RRRR-MM-DDTGG:MM", label=label)


def punch_json(p, tz):
    return {"id": p.pk, "employee": str(p.employee_id), "kind": p.kind, "kind_label": tr(p.get_kind_display()),
            "at": p.at.isoformat(), "local": p.at.astimezone(tz).strftime("%Y-%m-%d %H:%M"), "source": p.source,
            "source_label": tr(p.get_source_display()), "point": p.point.name if p.point else None, "note": p.note,
            "voids": p.voids_id, "voided": hasattr(p, "voided_by"),
            "recorded_by": p.recorded_by.get_username() if p.recorded_by and p.source == "manual" else None}


@transaction.atomic
def manual_punch(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    domain.body_object(data)
    e = employee_in(w, data.get("employee"), lock=True)
    require_manager(w, e)
    kind = data.get("kind")
    if kind not in ("in", "out"):
        raise DomainError("Rodzaj: wejście albo wyjście")
    tz = domain.zone(w.timezone)
    at = local_moment(data.get("at"), tz)
    if at > timezone.now() + timedelta(minutes=1):
        raise DomainError("Nie można wpisać odbicia w przyszłości")
    note = domain.text(data, "note", 200, True, "powód korekty")
    p = Punch.objects.create(workplace=w, employee=e, kind=kind, at=at, source="manual", recorded_by=user, note=note)
    return punch_json(p, tz)


@transaction.atomic
def void_punch(user, workplace_id, punch_id, data):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    p = Punch.objects.select_for_update().select_related("employee").filter(
        workplace=w, pk=punch_id if str(punch_id).isdigit() else 0).first()
    if not p or not sees(w, p.employee):
        raise DomainError("Odbicie: nie znaleziono", 404)
    require_manager(w, p.employee)
    if p.kind == "void":
        raise DomainError("To jest już wpis anulujący")
    if Punch.objects.filter(voids=p).exists():
        raise DomainError("To odbicie jest już anulowane", 409)
    note = domain.text(domain.body_object(data), "note", 200, True, "powód anulowania")
    v = Punch.objects.create(workplace=w, employee=p.employee, kind="void", at=timezone.now(), source="manual",
                             voids=p, recorded_by=user, note=note)
    return punch_json(v, domain.zone(w.timezone))


# --- sessions per day ---------------------------------------------------------------------------

def day_sessions(w, people, first, last):
    """{employee_id: {date: [session]}} for sessions starting (or, without an entry, ending) in [first, last]."""
    tz = domain.zone(w.timezone)
    since = datetime.combine(first - timedelta(days=1), datetime.min.time(), tz)
    until = datetime.combine(last + timedelta(days=2), datetime.min.time(), tz)
    by_person = defaultdict(list)
    for p in Punch.objects.filter(employee__in=people, at__range=(since, until)).order_by("at", "pk"):
        by_person[p.employee_id].append(p)
    voids = Punch.objects.filter(employee__in=people, kind="void", voids__at__range=(since, until))
    for v in voids:  # a void made later still cancels a punch in the window
        if v not in by_person[v.employee_id]:
            by_person[v.employee_id].append(v)
    now = timezone.now()
    result = defaultdict(lambda: defaultdict(list))
    for employee_id, punches in by_person.items():
        for s in domain.sessions(punches, now, settings.MAX_SHIFT_HOURS):
            day = (s["start"] or s["end"]).astimezone(tz).date()
            if first <= day <= last:
                result[employee_id][day].append(s)
    return result


def session_json(s, tz):
    return {"start": local_hm(s["start"], tz) if s["start"] else None, "end": local_hm(s["end"], tz) if s["end"] else None,
            "minutes": domain.worked_minutes(s), "problem": s["problem"] and tr(s["problem"]), "ongoing": s["start"] and not s["end"] and not s["problem"]}


def month_bounds(params, w):
    raw = params.get("month") or domain.local_today(w.timezone).strftime("%Y-%m")
    try:
        year, month = (int(x) for x in raw.split("-")) if isinstance(raw, str) and len(raw) == 7 else (0, 0)
        first = date(year, month, 1)
    except ValueError:
        raise DomainError("Miesiąc w formacie RRRR-MM") from None
    return first, first.replace(day=calendar.monthrange(year, month)[1])


def time_people(w, params):
    """Whose hours the caller may read: the people they manage, or just themselves."""
    people = [e for e in w.employees.select_related("department").order_by("department__name", "name")
              if manages(w, e) or (w.me and e.pk == w.me.pk)]
    if params.get("department"):
        people = [e for e in people if str(e.department_id) == params["department"]]
    if params.get("employee"):
        people = [e for e in people if str(e.id) == params["employee"]]
    return people


def report(user, workplace_id, params):
    w = workplace_access(user, workplace_id)
    first, last = month_bounds(params, w)
    tz = domain.zone(w.timezone)
    people = time_people(w, params)
    worked = day_sessions(w, people, first, last)
    planned = defaultdict(lambda: defaultdict(list))
    for s in Shift.objects.filter(employee__in=people, date__range=(first, last)):
        planned[s.employee_id][s.date].append(s)
    rows = []
    for e in people:
        days = []
        for i in range((last - first).days + 1):
            d = first + timedelta(days=i)
            shifts, sessions = planned[e.pk][d], worked[e.pk][d]
            if shifts or sessions:
                days.append({
                    "date": d.isoformat(), "shifts": [shift_json(s) for s in shifts],
                    "sessions": [session_json(s, tz) for s in sessions],
                    "planned": sum(domain.shift_minutes(s.start_time, s.end_time) for s in shifts),
                    "worked": sum(domain.worked_minutes(s) for s in sessions),
                })
        if not days and not e.active:
            continue
        rows.append({
            "employee": str(e.id), "name": e.name, "department": e.department.name if e.department else None,
            "planned": sum(d["planned"] for d in days), "worked": sum(d["worked"] for d in days),
            "problems": sum(1 for d in days for s in d["sessions"] if s["problem"]), "days": days,
        })
    return {"month": first.strftime("%Y-%m"), "first": first.isoformat(), "last": last.isoformat(), "people": rows}


def hours(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


def report_csv(user, workplace_id, params):
    """One row per person and day — for the accountant's spreadsheet. ; separator, Polish Excel default."""
    data = report(user, workplace_id, params)
    out = io.StringIO()
    out.write("﻿")  # Excel reads UTF-8 only with the BOM
    writer = csv.writer(out, delimiter=";")
    writer.writerow([tr("Data"), tr("Pracownik"), tr("Dział"), tr("Plan"), tr("Plan (godz.)"), tr("Odbicia"),
                     tr("Przepracowane (godz.)"), tr("Uwagi")])
    for person in data["people"]:
        for d in person["days"]:
            writer.writerow([
                d["date"], person["name"], person["department"] or "",
                ", ".join(f"{s['start']}–{s['end']}" for s in d["shifts"]), hours(d["planned"]),
                ", ".join(f"{s['start'] or '?'}–{s['end'] or '?'}" for s in d["sessions"]), hours(d["worked"]),
                ", ".join(s["problem"] for s in d["sessions"] if s["problem"]),  # translated by report()
            ])
        writer.writerow([tr("RAZEM"), person["name"], person["department"] or "", "", hours(person["planned"]), "",
                         hours(person["worked"]), tr("{count} do wyjaśnienia", count=person["problems"]) if person["problems"] else ""])
    return data["month"], out.getvalue()


def punches(user, workplace_id, params):
    """Raw events of one person in a month, voids included — what the corrections screen shows."""
    w = workplace_access(user, workplace_id)
    e = employee_in(w, params.get("employee"))
    if not manages(w, e) and not (w.me and e.pk == w.me.pk):
        raise DomainError("Odbicia widzi sama osoba i jej kierownik", 403)
    first, last = month_bounds(params, w)
    tz = domain.zone(w.timezone)
    qs = e.punches.filter(at__range=(datetime.combine(first, datetime.min.time(), tz),
                                     datetime.combine(last + timedelta(days=1), datetime.min.time(), tz)))
    return [punch_json(p, tz) for p in qs.select_related("point", "recorded_by", "voided_by").order_by("at", "pk")]


# --- today: the dashboard -------------------------------------------------------------------------

def status_of(e, now, tz):
    last = last_effective(e)
    inside = domain.next_kind(last, now, settings.MAX_SHIFT_HOURS) == "out"
    return {"inside": inside, "since": local_hm(last.at, tz) if inside else None,
            "last": {"kind": last.kind, "local": last.at.astimezone(tz).strftime("%Y-%m-%d %H:%M")} if last else None}


def today(user, workplace_id):
    w = workplace_access(user, workplace_id)
    tz = domain.zone(w.timezone)
    now = timezone.now()
    day = now.astimezone(tz).date()
    result = {"date": day.isoformat(), "me": None, "presence": None}
    if w.me:
        upcoming = w.me.shifts.filter(date__range=(day, day + timedelta(days=13)))
        result["me"] = {**status_of(w.me, now, tz), "shifts": [shift_json(s) for s in upcoming],
                        "unavailability": [u for u in w.me.unavailabilities.filter(date_to__gte=day).values(
                            "date_from", "date_to", "kind")]}
    managed = [e for e in visible_people(w) if manages(w, e)]
    if managed:
        planned = defaultdict(list)
        for s in Shift.objects.filter(employee__in=managed, date=day):
            planned[s.employee_id].append(f"{hm(s.start_time)}–{hm(s.end_time)}")
        result["presence"] = [{"employee": str(e.id), "name": e.name, "department": str(e.department_id) if e.department_id else None,
                               "today": planned[e.pk], **status_of(e, now, tz)} for e in managed]
    return result
