"""Infrastructure boundaries: session login, audit trail, bounded JSON, private caching."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import LoginEvent
from .signals import client_ip
from .transport import bounded_json
from .domain_errors import DomainError

PASSWORD = "A-long-unusual-phrase-74!"


class SessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user("dyrektor", password=PASSWORD)
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/session/").json()["csrf"]

    def login(self, username="dyrektor", password=PASSWORD, **extra):
        return self.client.post(
            "/api/session/",
            {"username": username, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf,
            **extra,
        )

    def test_login_logout_roundtrip_is_audited(self):
        response = self.login(HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.1", HTTP_USER_AGENT="TV")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"], "dyrektor")
        self.assertNotIn("password", response.json())
        self.client.delete("/api/session/", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual(self.client.get("/api/session/").json()["user"], None)
        kinds = list(LoginEvent.objects.order_by("created_at", "id").values_list("kind", "ip", "user_agent"))
        self.assertEqual(kinds, [("login", "203.0.113.7", "TV"), ("logout", "127.0.0.1", "")])

    def test_failed_login_records_username_even_without_user(self):
        self.assertEqual(self.login("nie-ma-takiego").status_code, 400)
        self.assertEqual(self.login(password="zle-haslo").status_code, 400)
        events = LoginEvent.objects.filter(kind="failed")
        self.assertEqual(sorted(events.values_list("username", flat=True)), ["dyrektor", "nie-ma-takiego"])
        self.assertTrue(all(e.user_id is None for e in events))
        self.assertEqual(self.client.get("/api/session/").json()["user"], None)

    def test_login_without_csrf_is_rejected_and_not_logged_in(self):
        response = self.client.post(
            "/api/session/", {"username": "dyrektor", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(LoginEvent.objects.filter(kind="login").exists())

    def test_malformed_fields_are_rejected_without_side_effects(self):
        for body in ([], "x", {"username": 1, "password": PASSWORD},
                     {"username": "a" * 151, "password": PASSWORD},
                     {"username": "dyrektor", "password": "x" * 4097},
                     {"username": "", "password": ""}, {"username": "   ", "password": "   "}):
            response = self.client.post("/api/session/", body, format="json", HTTP_X_CSRFTOKEN=self.csrf)
            self.assertEqual(response.status_code, 400, body)
        self.assertFalse(LoginEvent.objects.filter(kind="login").exists())

    def test_login_attempts_are_throttled(self):
        from unittest import mock
        from .views import LoginThrottle

        with mock.patch.object(LoginThrottle, "rate", "3/minute", create=True):
            codes = [self.login(password="zle-haslo").status_code for _ in range(4)]
        self.assertEqual(codes, [400, 400, 400, 429])

    def test_api_responses_are_private(self):
        response = self.client.get("/api/session/")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_health_needs_no_session(self):
        self.assertEqual(APIClient().get("/api/health/").json(), {"status": "ok"})


class LoginEventImmutabilityTests(TestCase):
    def test_cannot_update_or_delete(self):
        event = LoginEvent.objects.create(kind="failed", username="x")
        event.username = "y"
        with self.assertRaises(PermissionError):
            event.save()
        with self.assertRaises(PermissionError):
            event.delete()
        self.assertEqual(LoginEvent.objects.get().username, "x")

    def test_admin_offers_no_mutation(self):
        from django.contrib.admin.sites import site

        admin = site._registry[LoginEvent]
        self.assertFalse(admin.has_add_permission(None))
        self.assertFalse(admin.has_change_permission(None))
        self.assertFalse(admin.has_delete_permission(None))


class ClientIpTests(TestCase):
    def ip(self, **meta):
        from django.test import RequestFactory

        return client_ip(RequestFactory().get("/", **meta))

    def test_forwarded_first_then_remote_addr(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR="198.51.100.1, 10.0.0.2"), "198.51.100.1")
        self.assertEqual(self.ip(REMOTE_ADDR="192.0.2.5"), "192.0.2.5")
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR="  ", REMOTE_ADDR="192.0.2.5"), "192.0.2.5")

    def test_garbage_ip_is_dropped_not_stored(self):
        self.assertIsNone(self.ip(HTTP_X_FORWARDED_FOR="<script>", REMOTE_ADDR=""))


class BoundedJsonTests(TestCase):
    def test_rejects_nul_nonfinite_and_deep_structures(self):
        for value in ("a\x00b", {"k\x00": 1}, float("nan"), float("inf")):
            with self.assertRaises(DomainError):
                bounded_json(value)
        deep = []
        for _ in range(40):
            deep = [deep]
        with self.assertRaises(DomainError):
            bounded_json(deep)
        self.assertEqual(bounded_json({"a": [1, 2.5, None, True, "ok"]}), {"a": [1, 2.5, None, True, "ok"]})

    def test_oversized_body_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/session/").json()["csrf"]
        body = '{"username": "' + "a" * (600 * 1024) + '"}'
        response = client.post("/api/session/", body, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 400)


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/session/").json()["csrf"]

    def register(self, headers=None, **fields):
        body = {"email": "Szef@Hotel.PL", "password": PASSWORD, "firm": "Bistro Testowe", "name": "Anna Szef", "accept": True, **fields}
        return self.client.post("/api/register/", body, format="json", HTTP_X_CSRFTOKEN=self.csrf, **(headers or {}))

    def test_register_creates_director_firm_and_proof_then_logs_in(self):
        from grafik.models import Employee, Workplace
        from .accounts import terms
        from .models import TermsAcceptance

        response = self.register({"HTTP_X_FORWARDED_FOR": "203.0.113.9"})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["user"], "szef@hotel.pl")
        firm = Workplace.objects.get(pk=response.json()["workplace"])
        me = Employee.objects.get(workplace=firm)
        self.assertEqual((me.role, me.name, me.user.username), ("dyrektor", "Anna Szef", "szef@hotel.pl"))
        proof = TermsAcceptance.objects.get()
        self.assertEqual((proof.version, proof.sha256, proof.ip), (terms()["version"], terms()["sha256"], "203.0.113.9"))
        self.assertEqual(self.client.get("/api/workplaces/").json()[0]["role"], "dyrektor")
        # the e-mail logs in whatever its letter case
        fresh = APIClient()
        token = fresh.get("/api/session/").json()["csrf"]
        login = fresh.post("/api/session/", {"username": " SZEF@hotel.pl", "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login.status_code, 200)

    def test_bad_registrations_create_nothing(self):
        from grafik.models import Workplace

        cases = [
            ({"accept": False}, 400), ({"accept": "true"}, 400), ({"email": "nie-email"}, 400),
            ({"email": ""}, 400), ({"firm": "   "}, 400), ({"name": ""}, 400), ({"password": "krotkie"}, 400),
            ({"password": "szef@hotel.pl1"}, 400), ({"website": "http://spam"}, 400),
            ({"email": ["x"]}, 400), ({"firm": "x" * 201}, 400), ({"name": ["x"]}, 400),
        ]
        for fields, status in cases:
            cache.clear()  # every POST counts towards the hourly limit, failed ones too
            with self.subTest(fields=fields):
                self.assertEqual(self.register(**fields).status_code, status)
        self.assertFalse(Workplace.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_existing_email_and_missing_csrf(self):
        self.assertEqual(self.register().status_code, 201)
        self.client.delete("/api/session/", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.csrf = self.client.get("/api/session/").json()["csrf"]
        self.assertEqual(self.register(email="szef@hotel.pl").status_code, 409)
        anonymous = APIClient(enforce_csrf_checks=True)
        response = anonymous.post("/api/register/", {"email": "a@b.pl", "password": PASSWORD, "firm": "H", "name": "A", "accept": True}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_registration_is_throttled(self):
        for n in range(5):
            self.register(email=f"r{n}@hotel.pl")
            self.client.delete("/api/session/", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
            self.csrf = self.client.get("/api/session/").json()["csrf"]
        self.assertEqual(self.register(email="r9@hotel.pl").status_code, 429)

    @override_settings(DEMO_MAX=0)  # the server .env switches the demo on; this test is about the defaults
    def test_terms_and_public_config_are_public(self):
        anonymous = APIClient()
        terms = anonymous.get("/api/terms/").json()
        self.assertIn("Usługodawca", terms["html"])
        self.assertRegex(terms["version"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(anonymous.get("/api/public-config/").json(), {"ga_measurement_id": "", "demo": False})


class PasswordChangeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user("dyrektor", password=PASSWORD)
        self.client = APIClient()
        self.client.force_login(self.user)

    def change(self, current, new):
        return self.client.post("/api/me/password/", {"current": current, "new": new}, format="json")

    def test_change_requires_current_and_a_strong_new_one(self):
        self.assertEqual(self.change("zle", "Inne-dlugie-haslo-2026!").status_code, 400)
        self.assertEqual(self.change(PASSWORD, "123").status_code, 400)
        self.assertEqual(self.change(PASSWORD, None).status_code, 400)
        self.assertEqual(self.change(PASSWORD, "Inne-dlugie-haslo-2026!").status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Inne-dlugie-haslo-2026!"))
        self.assertEqual(self.client.get("/api/session/").json()["user"], "dyrektor")  # still logged in here

    def test_anonymous_cannot_change(self):
        self.assertEqual(APIClient().post("/api/me/password/", {"current": PASSWORD, "new": "x"}, format="json").status_code, 403)


class RetentionTests(TestCase):
    def test_dry_run_counts_and_real_run_deletes_only_old(self):
        from datetime import timedelta
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command
        from django.utils import timezone

        old_time = timezone.now() - timedelta(days=400)
        with mock.patch("django.utils.timezone.now", return_value=old_time):
            LoginEvent.objects.create(kind="failed", username="stary")
        LoginEvent.objects.create(kind="failed", username="nowy")
        out = StringIO()
        call_command("retencja_danych", "--dry-run", stdout=out)
        self.assertIn("1 do usunięcia", out.getvalue())
        self.assertEqual(LoginEvent.objects.count(), 2)
        call_command("retencja_danych", stdout=StringIO())
        self.assertEqual(list(LoginEvent.objects.values_list("username", flat=True)), ["nowy"])


class EnglishTests(TestCase):
    """Every Polish message the API can send has an English twin with the same {params} (core.i18n)."""

    APPS = ["core", "grafik"]  # every module of these apps except the tests: a new file is scanned on its own
    # call → (positional index, keyword) of the field label it turns into a message
    LABELS = {"identifier": (1, "what"), "text": (4, "label"), "calendar_day": (1, "label"),
              "clock_time": (1, "label"), "local_moment": (2, "label")}
    PROBLEMS = ["brak wyjścia", "wyjście bez wejścia"]  # domain.sessions, translated where reports are built

    @staticmethod
    def keys():
        import ast
        from pathlib import Path

        from django.apps import apps
        from django.conf import settings

        found = set(EnglishTests.PROBLEMS)
        sources = [f for app in EnglishTests.APPS for f in (Path(settings.BASE_DIR) / app).glob("*.py") if f.name != "tests.py"]
        for source in sources:
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = node.args.args[len(node.args.args) - len(node.args.defaults):]
                    found |= {d.value for a, d in zip(args, node.args.defaults)
                              if a.arg in ("label", "what") and isinstance(d, ast.Constant) and isinstance(d.value, str)}
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                strings = []
                if name in ("DomainError", "tr"):
                    strings = node.args[:1] + [k.value for k in node.keywords]
                elif name in EnglishTests.LABELS:
                    index, keyword = EnglishTests.LABELS[name]
                    strings = node.args[index:index + 1] + [k.value for k in node.keywords if k.arg == keyword]
                strings += [branch for s in strings if isinstance(s, ast.IfExp) for branch in (s.body, s.orelse)]
                found |= {s.value for s in strings if isinstance(s, ast.Constant) and isinstance(s.value, str)}
        for model in apps.get_app_config("grafik").get_models():
            if model.__name__.startswith("Historical"):
                continue  # simple-history rows are admin-only
            for field in model._meta.fields:
                found |= {str(label) for _, label in field.choices or ()}
        return found

    def test_every_message_has_english_with_the_same_params(self):
        import string

        from .i18n import english

        en = english()
        keys = self.keys()
        self.assertGreater(len(keys), 80)  # the scan itself works
        self.assertEqual(sorted(k for k in keys if k not in en), [])
        fields = lambda s: sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)
        self.assertEqual([k for k in keys if fields(k) != fields(en[k])], [])
        self.assertEqual(sorted(set(en) - keys), [])  # no dead entries

    def test_api_answers_in_the_chosen_language(self):
        client = APIClient()
        client.cookies["django_language"] = "en"
        self.assertEqual(client.post("/api/session/", {"username": "x", "password": "y"}, format="json").json()["error"],
                         "Incorrect login or password")
        self.assertIn("Polish version is binding", client.get("/api/terms/").json()["html"])
        polish = APIClient(HTTP_ACCEPT_LANGUAGE="pl")
        self.assertEqual(polish.post("/api/session/", {"username": "x", "password": "y"}, format="json").json()["error"],
                         "Nieprawidłowy login lub hasło")
        english_header = APIClient(HTTP_ACCEPT_LANGUAGE="en-GB,en;q=0.9")
        self.assertIn("binding", english_header.get("/api/terms/").json()["html"])

    def test_params_are_translated_and_unknown_text_stays_polish(self):
        from django.utils import translation

        from .i18n import error_body, tr

        with translation.override("en"):
            self.assertEqual(error_body(DomainError("Pole „{label}” jest wymagane", label="nazwa firmy"))["error"],
                             "The “company name” field is required")
            self.assertEqual(tr("Tekst bez tłumaczenia"), "Tekst bez tłumaczenia")
        with translation.override("pl"):
            self.assertEqual(str(DomainError("Pole „{label}” jest wymagane", label="uwagi")), "Pole „uwagi” jest wymagane")
