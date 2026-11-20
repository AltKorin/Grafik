"""Laws of grafik/events.py (#759): receptions from Kalendarz on the week; no answer is never an error."""
from datetime import date
from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings

from . import events, schedule
from .tests import World

ON = dict(KALENDARZ_URL="https://kalendarz.test", KONTO_API_CLIENT_ID="gid", KONTO_API_CLIENT_SECRET="gsek",
          OIDC_ISSUER="https://konto.test/o")
MON, SUN = date(2026, 11, 16), date(2026, 11, 22)
STYPA = {"id": 1, "data": "2026-11-21", "start": "13:00", "rodzaj": "Stypa", "goscie": 40, "status": "wstepna"}


def resp(status=200, body=None):
    r = mock.Mock(status_code=status)
    r.json.return_value = body
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


@override_settings(**ON)
class EventsLaws(TestCase):
    def setUp(self):
        cache.clear()
        self.world = World()
        self.w = self.world.x
        self.w.w_koncie = True
        self.w.save()
        self.post = mock.patch("grafik.events.requests.post",
                               return_value=resp(body={"access_token": "t1", "expires_in": 3600})).start()
        self.get = mock.patch("grafik.events.requests.get", return_value=resp(body={"przyjecia": [STYPA]})).start()
        self.addCleanup(mock.patch.stopall)

    def test_receptions_of_the_week(self):
        self.assertEqual(events.for_week(self.w, MON, SUN), [
            {"id": 1, "date": "2026-11-21", "start": "13:00", "kind": "Stypa", "guests": 40, "tentative": True}])
        params = self.get.call_args.kwargs["params"]
        self.assertEqual(params, {"firma": str(self.w.id), "od": "2026-11-16", "do": "2026-11-22"})
        self.assertEqual(self.get.call_args.kwargs["headers"], {"Authorization": "Bearer t1"})

    def test_week_endpoint_carries_them(self):
        week = schedule.week(self.world.user("ku"), self.w.id, {"week": "2026-11-18"})
        self.assertEqual(week["events"][0]["kind"], "Stypa")

    def test_cached_and_token_reused(self):
        events.for_week(self.w, MON, SUN)
        events.for_week(self.w, MON, SUN)
        events.for_week(self.w, date(2026, 11, 23), date(2026, 11, 29))
        self.assertEqual((self.post.call_count, self.get.call_count), (1, 2))

    def test_empty_week_is_a_list_not_none(self):
        self.get.return_value = resp(body={"przyjecia": []})
        self.assertEqual(events.for_week(self.w, MON, SUN), [])
        self.assertEqual(events.for_week(self.w, MON, SUN), [])  # from cache, still not "unavailable"

    def test_no_answer_is_no_section_never_an_error(self):
        for broken in (requests.Timeout(), requests.ConnectionError(), resp(503), resp(500), resp(200, {"x": 1}),
                       resp(200, {"przyjecia": [{"id": 1}]}), resp(200, None)):
            cache.clear()
            if isinstance(broken, Exception):
                self.get.side_effect, self.get.return_value = broken, None
            else:
                self.get.side_effect, self.get.return_value = None, broken
            with self.subTest(broken=broken), self.assertLogs("grafik.events", "WARNING"):
                self.assertIsNone(events.for_week(self.w, MON, SUN))

    def test_konto_down_is_no_section(self):
        self.post.side_effect = requests.ConnectionError()
        with self.assertLogs("grafik.events", "WARNING"):
            self.assertIsNone(events.for_week(self.w, MON, SUN))
        week = schedule.week(self.world.user("dx"), self.w.id, {"week": "2026-11-18"})
        self.assertIsNone(week["events"])
        self.assertIn("shifts", week)

    def test_failure_remembered_backpressure(self):
        self.get.side_effect = requests.Timeout()
        with self.assertLogs("grafik.events", "WARNING"):
            events.for_week(self.w, MON, SUN)
        events.for_week(self.w, MON, SUN)
        self.assertEqual(self.get.call_count, 1)

    def test_other_firms_kalendarz_is_quiet_and_long_cached(self):
        self.get.return_value = resp(404)
        with self.assertNoLogs("grafik.events", "WARNING"):
            self.assertIsNone(events.for_week(self.w, MON, SUN))
            self.assertIsNone(events.for_week(self.w, MON, SUN))
        self.assertEqual(self.get.call_count, 1)

    def test_401_drops_the_token(self):
        self.get.return_value = resp(401)
        with self.assertLogs("grafik.events", "WARNING"):
            events.for_week(self.w, MON, SUN)
        self.assertIsNone(cache.get(events.TOKEN_KEY))

    def test_firm_outside_konto_never_asks(self):
        self.w.w_koncie = False
        self.w.save()
        self.assertIsNone(events.for_week(self.w, MON, SUN))
        self.get.assert_not_called()

    def test_not_configured_never_asks(self):
        for missing in ("KALENDARZ_URL", "KONTO_API_CLIENT_ID", "OIDC_ISSUER"):
            with self.subTest(missing=missing), override_settings(**{missing: ""}):
                self.assertIsNone(events.for_week(self.w, MON, SUN))
        self.get.assert_not_called()
        self.post.assert_not_called()
