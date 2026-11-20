"""Receptions from Kalendarz przyjęć on the week view (OpenProject #759; Kalendarz API: #758).

The manager sees "Sat 21.11: Stypa 13:00, 40 guests" while planning shifts. Grafik asks Konto sudomie for an app
token (client credentials, scope `api`) and Kalendarz for the receptions of that firm and week.

Laws (grafik/test_events.py):
- not configured (no KALENDARZ_URL / Konto API client) or a firm outside Konto = None: the week has no section,
- Konto or Kalendarz down, slow, non-200 or garbage = None, never an exception: the week view still works,
- a failure is remembered for EVENTS_FAIL_TTL, so a dead Kalendarz does not slow down every week view (backpressure),
- 404 = this Kalendarz serves another firm: no section, remembered for EVENTS_TTL, not a warning,
- the app token is fetched once and reused until shortly before it expires.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)
TOKEN_KEY = "konto-api-token"


def enabled(w):
    return bool(settings.KALENDARZ_URL and settings.KONTO_API_CLIENT_ID and settings.OIDC_ISSUER and w.w_koncie)


def app_token():
    if token := cache.get(TOKEN_KEY):
        return token
    r = requests.post(settings.OIDC_ISSUER + "/token/", data={"grant_type": "client_credentials", "scope": "api"},
                      auth=(settings.KONTO_API_CLIENT_ID, settings.KONTO_API_CLIENT_SECRET),
                      timeout=settings.EVENTS_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    cache.set(TOKEN_KEY, body["access_token"], max(1, int(body.get("expires_in", 3600)) - 60))
    return body["access_token"]


def fetch(w, start, end):
    r = requests.get(settings.KALENDARZ_URL + "/api/przyjecia",
                     params={"firma": str(w.id), "od": start.isoformat(), "do": end.isoformat()},
                     headers={"Authorization": f"Bearer {app_token()}"}, timeout=settings.EVENTS_TIMEOUT)
    if r.status_code == 404:
        return None  # not this firm's Kalendarz
    if r.status_code == 401:
        cache.delete(TOKEN_KEY)  # revoked/expired early: the next view asks Konto for a new one
    r.raise_for_status()
    return [{"id": e["id"], "date": e["data"], "start": e["start"], "kind": e["rodzaj"], "guests": e["goscie"],
             "tentative": e["status"] == "wstepna"} for e in r.json()["przyjecia"]]


def for_week(w, start, end):
    """Receptions in [start, end] or None (no section)."""
    if not enabled(w):
        return None
    key = f"events:{w.id}:{start.isoformat()}"
    hit = cache.get(key)  # False = remembered failure; [] = a real week without receptions
    if hit is False:
        return None
    if hit is not None:
        return hit
    try:
        events = fetch(w, start, end)
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        log.warning("Kalendarz przyjęć unavailable for %s: %r", w.id, e)
        cache.set(key, False, settings.EVENTS_FAIL_TTL)
        return None
    cache.set(key, False if events is None else events, settings.EVENTS_TTL)
    return events
