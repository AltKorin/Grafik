"""Polish is the source text and the key; English lives in grafik/data/en.json (data, not code).

The language is Django's: LocaleMiddleware reads the `django_language` cookie set by the PL/EN switch,
then Accept-Language. Missing English falls back to Polish (tests require every key — see core.tests)."""

import json
from functools import cache
from pathlib import Path

from django.utils.translation import get_language

EN_FILE = Path(__file__).resolve().parent.parent / "grafik" / "data" / "en.json"
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"]


@cache
def english():
    return json.loads(EN_FILE.read_text(encoding="utf-8"))


def is_english():
    return (get_language() or "pl").startswith("en")


def tr(text, **params):
    """tr("Pole „{label}” jest wymagane", label="uwagi") → Polish or English; string params translate too."""
    if is_english():
        text = english().get(text, text)
        params = {k: english().get(v, v) if isinstance(v, str) else v for k, v in params.items()}
    return text.format(**params) if params else text


def error_body(error):
    return {"error": tr(error.template, **error.params)}
