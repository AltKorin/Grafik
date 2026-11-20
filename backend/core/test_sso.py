"""Logowanie kontem sudomie w Grafiku (#767) — prawa haka core.sso.role_z_konta i spięcie z panelem."""
import io
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.sso import role_z_konta
from core_sso import uslugi as sso
from core_sso.models import TozsamoscZewnetrzna
from grafik.models import Employee, Workplace

ISS = "https://konto.test/o"


def firma(w, rola):
    return {"id": str(w.id), "nazwa": w.name, "rola": rola, "wlasciciel": False}


class HakRol(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("marcin@x.pl", "marcin@x.pl", "x" * 12, first_name="Marcin")
        self.konto = Workplace.objects.create(name="Sami Swoi", w_koncie=True)
        self.lokalna = Workplace.objects.create(name="Tylko w Grafiku")

    def test_pierwsze_logowanie_zaklada_pracownika_z_rola(self):
        role_z_konta(self.u, [firma(self.konto, "kierownik")])
        e = Employee.objects.get(workplace=self.konto, user=self.u)
        self.assertEqual((e.role, e.name, e.active), ("kierownik", "Marcin", True))

    def test_kolejne_logowanie_aktualizuje_role_bez_duplikatu(self):
        role_z_konta(self.u, [firma(self.konto, "kierownik")])
        role_z_konta(self.u, [firma(self.konto, "dyrektor")])
        self.assertEqual(list(Employee.objects.filter(user=self.u).values_list("role", flat=True)), ["dyrektor"])

    def test_nieznana_firma_demo_i_zla_rola_pomijane(self):
        demo = Workplace.objects.create(name="Demo", demo_until=timezone.now() + timedelta(hours=1))
        role_z_konta(self.u, [{"id": "00000000-0000-0000-0000-000000000000", "nazwa": "x", "rola": "dyrektor", "wlasciciel": False},
                              firma(demo, "dyrektor"), firma(self.konto, "szef")])
        self.assertEqual(Employee.objects.filter(user=self.u).count(), 0)

    def test_odebrany_dostep_w_firmie_konta_wylacza_pracownika(self):
        role_z_konta(self.u, [firma(self.konto, "pracownik")])
        Employee.objects.create(workplace=self.lokalna, user=self.u, name="Marcin", role="pracownik")
        role_z_konta(self.u, [])
        self.assertFalse(Employee.objects.get(workplace=self.konto, user=self.u).active)
        self.assertTrue(Employee.objects.get(workplace=self.lokalna, user=self.u).active)  # firm spoza Konta nie ruszamy

    def test_nie_reaktywuje_zwolnionego_w_grafiku(self):
        Employee.objects.create(workplace=self.konto, user=self.u, name="Marcin", role="pracownik", active=False)
        role_z_konta(self.u, [firma(self.konto, "kierownik")])
        e = Employee.objects.get(workplace=self.konto, user=self.u)
        self.assertEqual((e.active, e.role), (False, "kierownik"))


@override_settings(OIDC_ISSUER=ISS, SSO_PRODUKT="grafik", SSO_FIRMA="", SSO_PO_ZALOGOWANIU="core.sso.role_z_konta")
class LogowanieKontem(TestCase):
    def setUp(self):
        self.w = Workplace.objects.create(name="Sami Swoi", w_koncie=True)

    def claims(self, sub="2", rola="dyrektor"):
        return {"sub": sub, "preferred_username": "biuro@x.pl", "name": "Marcin",
                "firmy": [{"id": str(self.w.id), "nazwa": "Sami Swoi", "produkty": {"grafik": rola, "kalendarz": "kierownik"}}]}

    def test_powiazane_konto_grafiku_wchodzi_bez_nowego_konta(self):
        stare = User.objects.create_user("biuro@x.pl", "biuro@x.pl", "x" * 12)
        Employee.objects.create(workplace=self.w, user=stare, name="Marcin", role="dyrektor")
        call_command("powiaz_konto", "biuro@x.pl", "2", "--firma", str(self.w.id), stdout=io.StringIO())
        u, firmy, blad = sso.konto_z_oidc(self.claims())
        self.assertIsNone(blad)
        self.assertEqual(u.pk, stare.pk)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(stare.check_password("x" * 12))  # stare hasło dalej działa (logowanie awaryjne)

    def test_bez_dostepu_do_grafiku_nie_wchodzi(self):
        c = self.claims()
        c["firmy"][0]["produkty"] = {"kalendarz": "kierownik"}
        self.assertIsNone(sso.konto_z_oidc(c)[0])
        self.assertEqual(User.objects.count(), 0)

    def test_powiaz_konto_bledy(self):
        User.objects.create_user("a@x.pl"), User.objects.create_user("b@x.pl")
        call_command("powiaz_konto", "a@x.pl", "9", stdout=io.StringIO())
        for args in (["b@x.pl", "9"], ["nikt@x.pl", "5"], ["a@x.pl", "9", "--firma", "00000000-0000-0000-0000-000000000000"]):
            with self.subTest(args=args), self.assertRaises(CommandError):
                call_command("powiaz_konto", *args, stdout=io.StringIO())
        self.assertEqual(TozsamoscZewnetrzna.objects.get(sub="9").user.username, "a@x.pl")

    def test_przycisk_tylko_z_flaga_i_komunikat_w_sesji(self):
        self.assertEqual(self.client.get("/api/public-config/").json()["sso"], {"nazwa": "Konto sudomie"})
        with self.settings(OIDC_ISSUER=""):
            self.assertIsNone(self.client.get("/api/public-config/").json()["sso"])
            self.assertEqual(self.client.get("/oidc/login/")["Location"], "/panel/")
        self.assertEqual(self.client.get("/api/session/").json()["komunikaty"], [])
