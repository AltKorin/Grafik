"""Input checks and the pure time arithmetic (no database): shift length, work sessions from punches."""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.domain_errors import DomainError
from core.transport import storage_string

DAY = 24 * 60


def body_object(data):
    if not isinstance(data, dict):
        raise DomainError("Oczekiwano obiektu JSON")
    return data


def identifier(value, what="Obiekt"):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise DomainError("{what}: nie znaleziono", 404, what=what) from None


def text(data, key, limit, required=False, label=None):
    value = data.get(key, "")
    label = label or key
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise DomainError("Pole „{label}”: oczekiwano tekstu", label=label)
    value = storage_string(value).strip()
    if required and not value:
        raise DomainError("Pole „{label}” jest wymagane", label=label)
    if len(value) > limit:
        raise DomainError("Pole „{label}”: maksymalnie {limit} znaków", label=label, limit=limit)
    return value


def calendar_day(value, label="data"):
    try:
        if isinstance(value, str) and len(value) == 10:
            return date.fromisoformat(value)
    except ValueError:
        pass
    raise DomainError("Pole „{label}”: data w formacie RRRR-MM-DD", label=label)


def clock_time(value, label="godzina"):
    try:
        if isinstance(value, str) and 4 <= len(value) <= 8:
            return time.fromisoformat(value).replace(second=0, microsecond=0)
    except ValueError:
        pass
    raise DomainError("Pole „{label}”: godzina w formacie GG:MM", label=label)


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise DomainError("Nieznana strefa czasowa") from None


def shift_minutes(start, end):
    """08:00–16:00 → 480, 22:00–06:00 → 480 (ends next day). Equal times are rejected by the validator."""
    return (end.hour * 60 + end.minute - start.hour * 60 - start.minute) % DAY


def shift_span(day, start, end, tz):
    begins = datetime.combine(day, start, tz)
    return begins, begins + timedelta(minutes=shift_minutes(start, end))


def week_start(day):
    return day - timedelta(days=day.weekday())


def effective(punches):
    """Drop `void` rows and the punches they cancel. Input in time order."""
    voided = {p.voids_id for p in punches if p.kind == "void"}
    return [p for p in punches if p.kind != "void" and p.pk not in voided]


def next_kind(last, now, max_hours):
    """Wejście unless the person is inside: last effective punch was an entry less than max_hours ago."""
    if last and last.kind == "in" and now - last.at < timedelta(hours=max_hours):
        return "out"
    return "in"


def sessions(punches, now, max_hours):
    """Pair entries with exits. Problems are named for the manager, never guessed away:
    an entry with no exit, an exit with no entry."""
    result, open_ = [], None

    def close(end, out=None, problem=None):
        result.append({"start": open_.at if open_ else None, "end": end, "in": open_.pk if open_ else None,
                       "out": out, "problem": problem})

    for p in effective(punches):
        if p.kind == "in":
            if open_:
                close(None, problem="brak wyjścia")
            open_ = p
        elif open_:
            close(p.at, out=p.pk)
            open_ = None
        else:
            close(p.at, out=p.pk, problem="wyjście bez wejścia")
    if open_:
        ongoing = now - open_.at < timedelta(hours=max_hours)
        close(None, problem=None if ongoing else "brak wyjścia")
    return result


def worked_minutes(session):
    if session["start"] and session["end"]:
        return int((session["end"] - session["start"]).total_seconds() // 60)
    return 0


def local_now(tz_name):
    from django.utils import timezone

    return timezone.now().astimezone(zone(tz_name))


def local_today(tz_name):
    return local_now(tz_name).date()
