"""What the director manages in the panel: the firm, departments, people (login, NFC card), clock points.

CLAUDE.md: everything the client manages has list / add / edit / delete in the client panel;
seed_demo only seeds it.
"""

import hashlib
import re
import secrets

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.domain_errors import DomainError
from core.models import LoginEvent, TermsAcceptance

from . import domain
from .access import is_director, workplace_access
from .models import ChangeRequest, ClockPoint, Department, Employee, Punch, Shift, Unavailability, Workplace

LOGIN = re.compile(r"[A-Za-z0-9_.-]{3,40}")
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
CARD = re.compile(r"[0-9A-Z]{4,64}")
UNKNOWN_CARDS = 5  # last unknown taps per firm, offered in the panel for assigning


def token():
    return secrets.token_urlsafe(32)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_card(value):
    """Readers type the UID with or without separators; Web NFC gives „04:a2:…”. One canonical form."""
    uid = re.sub(r"[\s:.-]", "", value).upper() if isinstance(value, str) else ""
    if not CARD.fullmatch(uid):
        raise DomainError("Numer karty: 4–64 znaki, cyfry i litery")
    return uid


# --- firm ------------------------------------------------------------------------------------

def workplace_json(w):
    return {"id": str(w.id), "name": w.name, "timezone": w.timezone, "role": getattr(w, "role", None),
            "me": str(w.me.id) if getattr(w, "me", None) else None,
            "department": str(w.me.department_id) if getattr(w, "me", None) and w.me.department_id else None}


def list_workplaces(user):
    from .access import workplaces_for

    return [workplace_json(workplace_access(user, w.id)) for w in workplaces_for(user)]


@transaction.atomic
def update_workplace(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    domain.body_object(data)
    w.name = domain.text(data, "name", 200, True, "nazwa firmy")
    if "timezone" in data:
        w.timezone = domain.text(data, "timezone", 64, True, "strefa czasowa")
        domain.zone(w.timezone)
    w.save(update_fields=["name", "timezone"])
    return workplace_json(w)


# --- departments -----------------------------------------------------------------------------

def department_json(d):
    return {"id": str(d.id), "name": d.name, "color": d.color, "people": d.employees.filter(active=True).count()}


def list_departments(user, workplace_id):
    w = workplace_access(user, workplace_id)
    return [department_json(d) for d in w.departments.order_by("name")]


def department_in(w, department_id):
    d = w.departments.filter(pk=domain.identifier(department_id, "Dział")).first()
    if not d:
        raise DomainError("Dział: nie znaleziono", 404)
    return d


def department_values(data):
    domain.body_object(data)
    color = data.get("color", "#5b7a8c")
    if not isinstance(color, str) or not COLOR.fullmatch(color):
        raise DomainError("Kolor w formacie #RRGGBB")
    return {"name": domain.text(data, "name", 80, True, "nazwa działu"), "color": color.lower()}


def save_department(d):
    try:
        with transaction.atomic():
            d.save()
    except IntegrityError:
        raise DomainError("Taki dział już istnieje", 409) from None
    return department_json(d)


@transaction.atomic
def create_department(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    return save_department(Department(workplace=w, **department_values(data)))


@transaction.atomic
def update_department(user, workplace_id, department_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    d = department_in(w, department_id)
    for key, value in department_values(data).items():
        setattr(d, key, value)
    return save_department(d)


@transaction.atomic
def delete_department(user, workplace_id, department_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    d = department_in(w, department_id)
    people = list(d.employees.filter(active=True).values_list("name", flat=True))
    if people:
        raise DomainError("W dziale są osoby: {people}. Przenieś je do innego działu, wtedy dział da się usunąć.", 409,
                          people=", ".join(people))
    d.delete()  # archived people keep working records, just without a department (SET_NULL)
    return {"deleted": True}


# --- people ----------------------------------------------------------------------------------

def employee_json(e, w):
    account = e.user
    return {
        "id": str(e.id), "name": e.name, "role": e.role, "active": e.active,
        "department": str(e.department_id) if e.department_id else None,
        "card": f"…{e.card_uid[-4:]}" if e.card_uid else None,
        "login": account.get_username() if account else None,
        "last_login": account.last_login.isoformat() if account and account.last_login else None,
        "me": bool(getattr(w, "me", None)) and e.pk == w.me.pk,
    }


def list_employees(user, workplace_id):
    from .access import sees

    w = workplace_access(user, workplace_id)
    people = w.employees.select_related("user").order_by("-active", "name")
    return [employee_json(e, w) for e in people if is_director(w) or (e.active and sees(w, e))]


def staff_member(w, employee_id):
    e = w.employees.select_related("user").filter(pk=domain.identifier(employee_id, "Pracownik")).first()
    if not e:
        raise DomainError("Pracownik: nie znaleziono", 404)
    return e


def employee_values(data, w):
    domain.body_object(data)
    role = data.get("role", "pracownik")
    if role not in dict(Employee.ROLES):
        raise DomainError("Rola: dyrektor, kierownik albo pracownik")
    department = department_in(w, data["department"]) if data.get("department") else None
    if role == "kierownik" and not department:
        raise DomainError("Kierownik musi mieć dział — to jego zespół")
    return {"name": domain.text(data, "name", 120, True, "imię i nazwisko"), "role": role, "department": department}


def keep_a_director(w, e):
    others = w.employees.filter(role="dyrektor", active=True).exclude(pk=e.pk)
    if e.role == "dyrektor" and e.active and not others.exists():
        raise DomainError("Firma musi mieć przynajmniej jednego aktywnego dyrektora", 409)


@transaction.atomic
def create_employee(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = Employee.objects.create(workplace=w, **employee_values(data, w))
    result = employee_json(e, w)
    if data.get("login"):
        result = give_account(user, workplace_id, e.id, {"login": data["login"]})
    return result


@transaction.atomic
def update_employee(user, workplace_id, employee_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    values = employee_values(data, w)
    if values["role"] != e.role:
        keep_a_director(w, e)
    for key, value in values.items():
        setattr(e, key, value)
    if "active" in data:
        if data["active"] is not True and data["active"] is not False:
            raise DomainError("Pole „aktywny”: tak albo nie")
        if not data["active"]:
            keep_a_director(w, e)
        e.active = data["active"]
    e.save()
    if not e.active:
        retire_account(e)
    return employee_json(e, w)


@transaction.atomic
def delete_employee(user, workplace_id, employee_id):
    """Someone with time records is archived (the firm must keep its time records); others go away."""
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    if w.me and e.pk == w.me.pk:
        raise DomainError("Nie możesz usunąć samego siebie", 409)
    keep_a_director(w, e)
    if e.punches.exists():
        e.active = False
        e.card_uid = ""
        e.save(update_fields=["active", "card_uid"])
        retire_account(e)
        e.shifts.filter(date__gte=domain.local_today(w.timezone)).delete()
        return {"deleted": False, "archived": True}
    account = e.user
    e.delete()
    if account:
        deactivate_if_unused(account)
    return {"deleted": True, "archived": False}


# --- login accounts --------------------------------------------------------------------------

def deactivate_if_unused(account):
    if not account.is_superuser and not account.employments.filter(active=True).exists():
        account.is_active = False
        account.save(update_fields=["is_active"])


def retire_account(e):
    if e.user:
        deactivate_if_unused(e.user)


@transaction.atomic
def give_account(user, workplace_id, employee_id, data):
    """New login with a generated password, or a new password for the existing one. Shown once."""
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    password = secrets.token_urlsafe(9)
    User = get_user_model()
    if e.user:
        account = e.user
    else:
        login = domain.body_object(data).get("login")
        if not isinstance(login, str) or not LOGIN.fullmatch(login.strip()):
            raise DomainError("Login: 3–40 znaków — litery bez polskich znaków, cyfry, kropka, myślnik, podkreślenie")
        login = login.strip().lower()
        account = User.objects.filter(username__iexact=login).first()
        # A person coming back gets their old account (history keeps one author); never take over a used one.
        if account and (account.is_active or account.is_superuser or account.employments.exists()):
            raise DomainError("Ten login jest już zajęty — wybierz inny", 409)
        account = account or User.objects.create_user(login)
        e.user = account
        e.save(update_fields=["user"])
    account.set_password(password)
    account.is_active = True
    account.save()
    return {**employee_json(e, w), "password": password}


@transaction.atomic
def remove_account(user, workplace_id, employee_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    if w.me and e.pk == w.me.pk:
        raise DomainError("Nie możesz odebrać logowania samemu sobie", 409)
    account, e.user = e.user, None
    e.save(update_fields=["user"])
    if account:
        deactivate_if_unused(account)
    return employee_json(e, w)


# --- NFC cards -------------------------------------------------------------------------------

def remember_unknown_card(w, uid, point):
    key = f"unknown-cards:{w.id}"
    taps = [t for t in cache.get(key, []) if t["uid"] != uid]
    cache.set(key, [{"uid": uid, "at": timezone.now().isoformat(), "point": point.name}, *taps][:UNKNOWN_CARDS], 3600)


def unknown_cards(user, workplace_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    known = set(w.employees.exclude(card_uid="").values_list("card_uid", flat=True))
    return [t for t in cache.get(f"unknown-cards:{w.id}", []) if t["uid"] not in known]


@transaction.atomic
def assign_card(user, workplace_id, employee_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    uid = normalize_card(domain.body_object(data).get("uid"))
    holder = w.employees.filter(card_uid=uid).exclude(pk=e.pk).first()
    if holder:
        raise DomainError("Ta karta jest już przypisana: {name}. Najpierw odbierz ją tej osobie.", 409, name=holder.name)
    e.card_uid = uid
    e.save(update_fields=["card_uid"])
    return employee_json(e, w)


@transaction.atomic
def remove_card(user, workplace_id, employee_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    e = staff_member(w, employee_id)
    e.card_uid = ""
    e.save(update_fields=["card_uid"])
    return employee_json(e, w)


# --- clock points (sticker + optional kiosk) -------------------------------------------------

def point_json(p):
    return {"id": str(p.id), "name": p.name, "tag_path": f"/nfc/{p.tag_token}", "kiosk": bool(p.kiosk_hash),
            "punches": p.punch_set.count()}


def list_points(user, workplace_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    return [point_json(p) for p in w.clock_points.order_by("name")]


def point_in(w, point_id):
    p = w.clock_points.filter(pk=domain.identifier(point_id, "Punkt odbić")).first()
    if not p:
        raise DomainError("Punkt odbić: nie znaleziono", 404)
    return p


@transaction.atomic
def create_point(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    name = domain.text(domain.body_object(data), "name", 120, True, "nazwa punktu")
    return point_json(ClockPoint.objects.create(workplace=w, name=name, tag_token=token()))


@transaction.atomic
def update_point(user, workplace_id, point_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    p = point_in(w, point_id)
    p.name = domain.text(domain.body_object(data), "name", 120, True, "nazwa punktu")
    p.save(update_fields=["name"])
    return point_json(p)


@transaction.atomic
def delete_point(user, workplace_id, point_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    point_in(w, point_id).delete()  # punches stay, without a point (SET_NULL)
    return {"deleted": True}


@transaction.atomic
def new_tag(user, workplace_id, point_id):
    """The sticker's link leaked (someone punches from home): new link, the old sticker stops working."""
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    p = point_in(w, point_id)
    p.tag_token = token()
    p.save(update_fields=["tag_token"])
    return point_json(p)


@transaction.atomic
def new_kiosk(user, workplace_id, point_id):
    """Kiosk link with a secret — returned only now; a new one replaces the old (lost tablet)."""
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    p = point_in(w, point_id)
    secret = token()
    p.kiosk_hash = digest(secret)
    p.save(update_fields=["kiosk_hash"])
    return {**point_json(p), "kiosk_path": f"/kiosk/{secret}"}


@transaction.atomic
def remove_kiosk(user, workplace_id, point_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    p = point_in(w, point_id)
    p.kiosk_hash = ""
    p.save(update_fields=["kiosk_hash"])
    return point_json(p)


# --- the whole firm: export and deletion (RODO art. 17/20) ------------------------------------

def export_workplace(user, workplace_id):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    people = {e.pk: e.name for e in w.employees.all()}
    return {
        "firma": workplace_json(w),
        "dzialy": list_departments(user, workplace_id),
        "pracownicy": [employee_json(e, w) for e in w.employees.select_related("user").order_by("name")],
        "punkty_odbic": [{"name": p.name} for p in w.clock_points.order_by("name")],
        "zmiany": [{"pracownik": people[s.employee_id], "data": s.date.isoformat(), "od": s.start_time.strftime("%H:%M"),
                    "do": s.end_time.strftime("%H:%M"), "uwagi": s.notes}
                   for s in Shift.objects.filter(employee__workplace=w)],
        "niedyspozycyjnosc": [{"pracownik": people[u.employee_id], "od": u.date_from.isoformat(), "do": u.date_to.isoformat(),
                               "rodzaj": u.kind, "uwagi": u.note}
                              for u in Unavailability.objects.filter(employee__workplace=w)],
        "odbicia": [{"pracownik": people[p.employee_id], "rodzaj": p.kind, "czas": p.at.isoformat(), "zrodlo": p.source,
                     "anuluje": p.voids_id, "id": p.pk, "uwagi": p.note}
                    for p in w.punches.all()],
    }


def anonymize(account):
    """Account stops pointing at a person; its pk stays so nothing that referenced it breaks."""
    old = account.get_username()
    alias = f"usuniety-{account.pk}"
    account.username, account.email, account.first_name, account.last_name = alias, "", "", ""
    account.is_active = False
    account.set_unusable_password()
    account.save()
    LoginEvent.objects.filter(Q(user=account) | Q(user__isnull=True, username__iexact=old)).update(
        username=alias, ip=None, user_agent="")
    TermsAcceptance.objects.filter(user=account).update(ip=None)


def purge_history(workplace_id, employee_ids):
    """simple-history keeps old values and deletion rows — erasure that skips them erases nothing."""
    for model in (Shift, Unavailability, ChangeRequest):
        model.history.filter(employee_id__in=employee_ids).delete()
    for model in (Employee, Department, ClockPoint):
        model.history.filter(workplace_id=workplace_id).delete()
    Workplace.history.filter(id=workplace_id).delete()


@transaction.atomic
def delete_workplace(user, workplace_id, data):
    w = workplace_access(user, workplace_id, minimum="dyrektor")
    typed = domain.body_object(data).get("confirm")
    if not isinstance(typed, str) or typed.strip() != w.name.strip():
        raise DomainError("Wpisz dokładną nazwę firmy, żeby potwierdzić usunięcie")
    accounts = [e.user for e in w.employees.select_related("user") if e.user]
    employee_ids = list(Employee.history.filter(workplace_id=w.pk).values_list("id", flat=True).distinct())
    pk = w.pk
    w.delete()  # punches go with it: queryset cascade never calls Punch.delete()
    purge_history(pk, employee_ids)
    removed = [a for a in accounts if not a.is_superuser and not a.employments.exists()]
    for account in removed:
        anonymize(account)
    return {"deleted": True, "account_removed": any(a.pk == user.pk for a in removed)}
