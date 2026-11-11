"""Zapis do newslettera sudomie przy rejestracji (pole domyślnie niezaznaczone).

Flaga: bez NEWSLETTER_KLUCZ pole się nie pokazuje i nic nie wysyłamy.
Adres trafia do sudomie.pl (chat-api /newsletter) z kluczem tej aplikacji i IP użytkownika;
sudomie.pl wysyła mail z linkiem potwierdzającym i przechowuje dowód zgody. Tu nic nie zapisujemy.
RODO: podstawa art. 6 ust. 1 lit. a (zgoda), administrator listy: Komorowski & Windorpski sp. z o.o.
"""

import json
import logging
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


def wlaczony():
    return bool(settings.NEWSLETTER_KLUCZ)


def zapisz(email, ip):
    """Wołane po zatwierdzeniu rejestracji. Błąd sieci nie może popsuć rejestracji: tylko log."""
    body = json.dumps({"email": email, "ip": ip or ""}).encode()
    req = urllib.request.Request(
        settings.NEWSLETTER_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Newsletter-Klucz": settings.NEWSLETTER_KLUCZ},
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.NEWSLETTER_TIMEOUT) as response:
            return 200 <= response.status < 300
    except Exception:  # noqa: BLE001 — każdy błąd (sieć, 4xx, 5xx) kończy się tylko wpisem w logu
        log.exception("newsletter: nie udało się zapisać %s", email)
        return False
