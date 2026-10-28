"""Grafik: the week grid, shifts, unavailability, change requests (PLAN.md §3–4)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.domain_errors import DomainError
from core.i18n import MONTHS_EN, error_body, is_english, tr

from . import domain
from .access import employee_in, manages, require_manager, sees, workplace_access
from .models import ChangeRequest, Shift, Unavailability

MAX_UNAVAILABLE_DAYS = 366
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
          "października", "listopada", "grudnia"]


def hm(t):
    return t.strftime("%H:%M") if t else None


def day_label(d):
    return f"{d.day} {(MONTHS_EN if is_english() else MONTHS)[d.month - 1]}"


def range_label(a, b):
    return day_label(a) if a == b else f"{day_label(a)} – {day_label(b)}"


def shift_json(s):
    return {"id": str(s.id), "employee": str(s.employee_id), "date": s.date.isoformat(), "start": hm(s.start_time),
            "end": hm(s.end_time), "notes": s.notes, "minutes": domain.shift_minutes(s.start_time, s.end_time)}


def unavailability_json(u):
    return {"id": str(u.id), "employee": str(u.employee_id), "date_from": u.date_from.isoformat(),
            "date_to": u.date_to.isoformat(), "kind": u.kind, "kind_label": tr(u.get_kind_display()), "note": u.note}


def visible_people(w, department=None):
    people = w.employees.filter(active=True).select_related("department").order_by("department__name", "name")
    return [e for e in people if sees(w, e) and (not department or str(e.department_id) == department)]


# --- the week --------------------------------------------------------------------------------

def week(user, workplace_id, params):
    w = workplace_access(user, workplace_id)
    raw = params.get("week")
    start = domain.week_start(domain.calendar_day(raw, "tydzień") if raw else domain.local_today(w.timezone))
    end = start + timedelta(days=6)
    department = params.get("department") or None
    people = visible_people(w, department)
    return {
        "week": start.isoformat(),
        "days": [(start + timedelta(days=i)).isoformat() for i in range(7)],
        "today": domain.local_today(w.timezone).isoformat(),
        "people": [{"id": str(e.id), "name": e.name, "department": str(e.department_id) if e.department_id else None,
                    "editable": manages(w, e)} for e in people],
        "shifts": [shift_json(s) for s in Shift.objects.filter(employee__in=people, date__range=(start, end))],
        "unavailability": [unavailability_json(u) for u in Unavailability.objects.filter(
            employee__in=people, date_from__lte=end, date_to__gte=start)],
    }


# --- shifts ----------------------------------------------------------------------------------

def check_shift(w, employee, day, start, end, exclude=()):
    """The two blocks of PLAN.md §3: reported unavailability, and the same person twice at once."""
    if start == end:
        raise DomainError("Początek i koniec zmiany nie mogą być równe")
    away = employee.unavailabilities.filter(date_from__lte=day, date_to__gte=day).first()
    if away:
        raise DomainError(
            "{name} zgłosił(a): {kind} ({days}). Zmiany na ten dzień nie da się zapisać — poproś o wycofanie zgłoszenia.",
            409, name=employee.name, kind=away.get_kind_display(), days=range_label(away.date_from, away.date_to))
    tz = domain.zone(w.timezone)
    begins, ends = domain.shift_span(day, start, end, tz)
    nearby = employee.shifts.filter(date__range=(day - timedelta(days=1), day + timedelta(days=1))).exclude(pk__in=exclude)
    for other in nearby:
        a, b = domain.shift_span(other.date, other.start_time, other.end_time, tz)
        if a < ends and begins < b:
            raise DomainError("{name} ma już zmianę {day} {start}–{end}, która się nakłada", 409, name=employee.name,
                              day=day_label(other.date), start=hm(other.start_time), end=hm(other.end_time))


def shift_values(data, w):
    domain.body_object(data)
    employee = employee_in(w, data.get("employee"), lock=True)
    require_manager(w, employee)
    if not employee.active:
        raise DomainError("Ta osoba jest zarchiwizowana")
    return {
        "employee": employee,
        "date": domain.calendar_day(data.get("date")),
        "start_time": domain.clock_time(data.get("start"), "od"),
        "end_time": domain.clock_time(data.get("end"), "do"),
        "notes": domain.text(data, "notes", 200, label="uwagi"),
    }


def shift_in(w, shift_id, lock=False):
    qs = Shift.objects.select_for_update() if lock else Shift.objects
    s = qs.select_related("employee").filter(employee__workplace=w, pk=domain.identifier(shift_id, "Zmiana")).first()
    if not s or not sees(w, s.employee):
        raise DomainError("Zmiana: nie znaleziono", 404)
    return s


@transaction.atomic
def create_shift(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    v = shift_values(data, w)
    check_shift(w, v["employee"], v["date"], v["start_time"], v["end_time"])
    return shift_json(Shift.objects.create(**v))


@transaction.atomic
def update_shift(user, workplace_id, shift_id, data):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    s = shift_in(w, shift_id, lock=True)
    require_manager(w, s.employee)
    v = shift_values({"employee": str(s.employee_id), **domain.body_object(data)}, w)
    check_shift(w, v["employee"], v["date"], v["start_time"], v["end_time"], exclude=[s.pk])
    for key, value in v.items():
        setattr(s, key, value)
    s.save()
    return shift_json(s)


@transaction.atomic
def delete_shift(user, workplace_id, shift_id):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    s = shift_in(w, shift_id, lock=True)
    require_manager(w, s.employee)
    s.delete()
    return {"deleted": True}


@transaction.atomic
def copy_week(user, workplace_id, data):
    """Last week's shifts into this week, for the people the caller manages; conflicts are skipped and named."""
    w = workplace_access(user, workplace_id, minimum="kierownik")
    target = domain.week_start(domain.calendar_day(domain.body_object(data).get("week"), "tydzień"))
    copied, skipped = 0, []
    for s in Shift.objects.filter(employee__workplace=w, employee__active=True,
                                  date__range=(target - timedelta(days=7), target - timedelta(days=1))).select_related("employee"):
        if not manages(w, s.employee):
            continue
        day = s.date + timedelta(days=7)
        try:
            with transaction.atomic():
                check_shift(w, s.employee, day, s.start_time, s.end_time)
                Shift.objects.create(employee=s.employee, date=day, start_time=s.start_time, end_time=s.end_time, notes=s.notes)
            copied += 1
        except DomainError as error:
            skipped.append(error_body(error)["error"])
    return {"copied": copied, "skipped": skipped}


# --- unavailability --------------------------------------------------------------------------

def own_or_managed(w, employee):
    if not (w.me and employee.pk == w.me.pk) and not manages(w, employee):
        raise DomainError("Niedyspozycyjność zgłasza sama osoba albo jej kierownik", 403)


def unavailability_values(data, w):
    domain.body_object(data)
    employee = employee_in(w, data.get("employee")) if data.get("employee") else w.me
    if not employee:
        raise DomainError("Wybierz osobę")
    own_or_managed(w, employee)
    date_from = domain.calendar_day(data.get("date_from"), "od")
    date_to = domain.calendar_day(data.get("date_to") or data.get("date_from"), "do")
    if date_to < date_from:
        raise DomainError("Koniec nie może być przed początkiem")
    if (date_to - date_from).days >= MAX_UNAVAILABLE_DAYS:
        raise DomainError("Najwyżej rok w jednym zgłoszeniu")
    kind = data.get("kind", "inne")
    if kind not in dict(Unavailability.KINDS):
        raise DomainError("Rodzaj: urlop, L4 albo niedostępność")
    return {"employee": employee, "date_from": date_from, "date_to": date_to, "kind": kind,
            "note": domain.text(data, "note", 200, label="uwagi")}


def with_conflicts(u):
    """Already planned shifts are not deleted — the manager sees them and decides."""
    clashes = u.employee.shifts.filter(date__range=(u.date_from, u.date_to))
    return {**unavailability_json(u), "conflicts": [shift_json(s) for s in clashes]}


def unavailability_in(w, unavailability_id):
    u = Unavailability.objects.select_related("employee").filter(
        employee__workplace=w, pk=domain.identifier(unavailability_id, "Zgłoszenie")).first()
    if not u or not sees(w, u.employee):
        raise DomainError("Zgłoszenie: nie znaleziono", 404)
    return u


def list_unavailability(user, workplace_id, params):
    w = workplace_access(user, workplace_id)
    qs = Unavailability.objects.filter(employee__workplace=w, date_to__gte=domain.local_today(w.timezone) - timedelta(days=60))
    if params.get("employee"):
        qs = qs.filter(employee=employee_in(w, params["employee"]))
    return [with_conflicts(u) for u in qs.select_related("employee").order_by("date_from") if sees(w, u.employee)]


@transaction.atomic
def create_unavailability(user, workplace_id, data):
    w = workplace_access(user, workplace_id)
    return with_conflicts(Unavailability.objects.create(**unavailability_values(data, w)))


@transaction.atomic
def update_unavailability(user, workplace_id, unavailability_id, data):
    w = workplace_access(user, workplace_id)
    u = unavailability_in(w, unavailability_id)
    own_or_managed(w, u.employee)
    for key, value in unavailability_values({"employee": str(u.employee_id), **domain.body_object(data)}, w).items():
        setattr(u, key, value)
    u.save()
    return with_conflicts(u)


@transaction.atomic
def delete_unavailability(user, workplace_id, unavailability_id):
    w = workplace_access(user, workplace_id)
    u = unavailability_in(w, unavailability_id)
    own_or_managed(w, u.employee)
    u.delete()  # the history table keeps the proof that it was reported
    return {"deleted": True}


# --- change requests -------------------------------------------------------------------------

def request_json(r, w):
    def brief(s):
        return {**shift_json(s), "name": s.employee.name} if s else None

    return {
        "id": str(r.id), "kind": r.kind, "kind_label": tr(r.get_kind_display()), "status": r.status,
        "status_label": tr(r.get_status_display()), "employee": str(r.employee_id), "name": r.employee.name,
        "shift": brief(r.shift), "swap_shift": brief(r.swap_shift),
        "new_date": r.new_date.isoformat() if r.new_date else None, "new_start": hm(r.new_start), "new_end": hm(r.new_end),
        "reason": r.reason, "review_note": r.review_note, "reviewed_by": r.reviewed_by.name if r.reviewed_by else None,
        "created_at": r.created_at.isoformat(), "mine": bool(w.me) and r.employee_id == w.me.pk,
        "reviewable": r.status == "pending" and manages(w, r.employee),
    }


def request_values(data, w, me):
    domain.body_object(data)
    kind = data.get("kind")
    if kind not in dict(ChangeRequest.KINDS):
        raise DomainError("Rodzaj wniosku: zamiana, odwołanie, zmiana godzin albo dodatkowa zmiana")
    today = domain.local_today(w.timezone)
    v = {"kind": kind, "shift": None, "swap_shift": None, "new_date": None, "new_start": None, "new_end": None,
         "reason": domain.text(data, "reason", 500, label="powód")}
    if kind in ("swap", "cancel", "modify"):
        shift = shift_in(w, data.get("shift"))
        if shift.employee_id != me.pk:
            raise DomainError("Wniosek dotyczy Twojej zmiany")
        if shift.date < today:
            raise DomainError("Ta zmiana już minęła")
        v["shift"] = shift
    if kind == "swap":
        other = shift_in(w, data.get("swap_shift"))
        if other.employee_id == me.pk:
            raise DomainError("Zamiana jest z cudzą zmianą")
        if other.date < today:
            raise DomainError("Zmiana do zamiany już minęła")
        v["swap_shift"] = other
    if kind in ("modify", "add"):
        v["new_date"] = domain.calendar_day(data.get("new_date"), "dzień")
        v["new_start"] = domain.clock_time(data.get("new_start"), "od")
        v["new_end"] = domain.clock_time(data.get("new_end"), "do")
        if v["new_date"] < today:
            raise DomainError("Ten dzień już minął")
        if v["new_start"] == v["new_end"]:
            raise DomainError("Początek i koniec zmiany nie mogą być równe")
    return v


def list_requests(user, workplace_id):
    w = workplace_access(user, workplace_id)
    qs = ChangeRequest.objects.filter(employee__workplace=w).select_related(
        "employee", "shift__employee", "swap_shift__employee", "reviewed_by")[:300]
    return [request_json(r, w) for r in qs if (w.me and r.employee_id == w.me.pk) or manages(w, r.employee)]


def mine(w):
    if not w.me:
        raise DomainError("Konto serwisowe nie składa wniosków", 403)
    return w.me


@transaction.atomic
def create_request(user, workplace_id, data):
    w = workplace_access(user, workplace_id)
    me = mine(w)
    return request_json(ChangeRequest.objects.create(employee=me, **request_values(data, w, me)), w)


def request_in(w, request_id):
    r = ChangeRequest.objects.select_for_update().filter(
        employee__workplace=w, pk=domain.identifier(request_id, "Wniosek")).first()
    if not r:
        raise DomainError("Wniosek: nie znaleziono", 404)
    return r


def pending(r):
    if r.status != "pending":  # approving twice must not apply twice (CLAUDE.md: idempotence)
        raise DomainError("Wniosek ma już status: {state}", 409, state=r.get_status_display())


@transaction.atomic
def update_request(user, workplace_id, request_id, data):
    w = workplace_access(user, workplace_id)
    me = mine(w)
    r = request_in(w, request_id)
    if r.employee_id != me.pk:
        raise DomainError("Wniosek: nie znaleziono", 404)
    pending(r)
    for key, value in request_values(data, w, me).items():
        setattr(r, key, value)
    r.save()
    return request_json(r, w)


@transaction.atomic
def withdraw_request(user, workplace_id, request_id):
    w = workplace_access(user, workplace_id)
    r = request_in(w, request_id)
    if not w.me or r.employee_id != w.me.pk:
        raise DomainError("Wniosek wycofuje osoba, która go złożyła", 403)
    pending(r)
    r.status = "withdrawn"
    r.save(update_fields=["status"])
    return request_json(r, w)


def apply(w, r):
    """Carry the request out on the schedule, with the same checks as a manager's own edit."""
    gone = DomainError("Zmiana z wniosku już nie istnieje — odrzuć wniosek", 409)
    if r.kind in ("swap", "cancel", "modify") and not r.shift:
        raise gone
    if r.kind == "cancel":
        shift, r.shift = r.shift, None  # the request's history keeps which shift it was
        shift.delete()
    elif r.kind == "modify":
        s = r.shift
        check_shift(w, s.employee, r.new_date, r.new_start, r.new_end, exclude=[s.pk])
        s.date, s.start_time, s.end_time = r.new_date, r.new_start, r.new_end
        s.save()
    elif r.kind == "add":
        check_shift(w, r.employee, r.new_date, r.new_start, r.new_end)
        Shift.objects.create(employee=r.employee, date=r.new_date, start_time=r.new_start, end_time=r.new_end,
                             notes="z wniosku")
    elif r.kind == "swap":
        a, b = r.shift, r.swap_shift
        if not b:
            raise gone
        require_manager(w, b.employee)
        a.employee, b.employee = b.employee, a.employee
        check_shift(w, a.employee, a.date, a.start_time, a.end_time, exclude=[a.pk, b.pk])
        check_shift(w, b.employee, b.date, b.start_time, b.end_time, exclude=[a.pk, b.pk])
        a.save()
        b.save()


@transaction.atomic
def review_request(user, workplace_id, request_id, data, approve):
    w = workplace_access(user, workplace_id, minimum="kierownik")
    r = request_in(w, request_id)
    require_manager(w, r.employee)
    pending(r)
    if approve:
        for s in (r.shift, r.swap_shift):
            if s:
                Shift.objects.select_for_update().filter(pk=s.pk).first()
        apply(w, r)
    r.status = "approved" if approve else "rejected"
    r.review_note = domain.text(domain.body_object(data), "note", 500, label="uwaga")
    r.reviewed_by = w.me
    r.reviewed_at = timezone.now()
    r.save()
    return request_json(ChangeRequest.objects.select_related("employee", "reviewed_by").get(pk=r.pk), w)

