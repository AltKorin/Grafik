"""Bistro Demo. One builder for `seed_demo` (a fixed demo firm on a server) and for the sandbox every visitor
gets from „Wypróbuj demo”: an own copy, accounts without passwords (only this session enters them), erased
after DEMO_HOURS. Switching „zobacz jako dyrektor / kierownik / pracownik” signs the session into that account."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as sign_in
from django.db import transaction
from django.utils import timezone

from core.domain_errors import DomainError

from . import domain, team
from .models import ClockPoint, Department, Employee, Punch, Shift, Unavailability, Workplace

NAME = "Bistro Demo"
PEOPLE = [  # login, name, department, role, card
    ("dyrektor-demo", "Dorota Dyrektor", None, "dyrektor", ""),
    ("kuchnia-kier", "Kamil Kierownik", "Kuchnia", "kierownik", ""),
    ("anna", "Anna Nowak", "Kuchnia", "pracownik", "04A1B2C3"),
    ("tomek", "Tomasz Wiśniewski", "Kuchnia", "pracownik", "04D4E5F6"),
    ("ola", "Aleksandra Lewandowska", "Sala", "pracownik", "0477AA11"),
    (None, "Piotr Zieliński", "Sala", "pracownik", "0488BB22"),  # card only, no phone
]
DEPARTMENTS = (("Kuchnia", "#c95a1e"), ("Sala", "#1e5f9b"))
HOURS = [("06:00", "14:00"), ("14:00", "22:00"), ("10:00", "18:00")]
SEEN_AS = {"dyrektor": "dyrektor-demo", "kierownik": "kuchnia-kier", "pracownik": "anna"}  # sandbox role → account
SESSION_KEY = "demo"


def build(password=None, prefix="", demo_until=None):
    """The firm with two departments, six people, two weeks of shifts, a leave, last week's punches and an NFC
    point with a kiosk. No password = accounts nobody can log in to with a password."""
    User = get_user_model()
    firm = Workplace.objects.create(name=NAME, demo_until=demo_until)
    depts = {n: Department.objects.create(workplace=firm, name=n, color=c) for n, c in DEPARTMENTS}
    people, accounts = [], {}
    for login, name, dept, role, card in PEOPLE:
        user = None
        if login:
            user = User.objects.filter(username=prefix + login).first() or User.objects.create_user(prefix + login)
            user.set_password(password) if password else user.set_unusable_password()
            user.is_active = True
            user.save()
            accounts[login] = user
        people.append(Employee.objects.create(workplace=firm, user=user, name=name, role=role,
                                              department=depts.get(dept), card_uid=card))
    today = domain.local_today(firm.timezone)
    monday = domain.week_start(today)
    for i, e in enumerate(people[1:]):
        for d in range(-7, 7):
            if (d + i) % 7 in (5, 6):
                continue
            start, end = HOURS[(i + (d // 7)) % len(HOURS)]
            Shift.objects.create(employee=e, date=monday + timedelta(days=d), start_time=start, end_time=end)
    tomek = people[3]
    leave = (monday + timedelta(days=9), monday + timedelta(days=11))
    Shift.objects.filter(employee=tomek, date__range=leave).delete()
    Unavailability.objects.create(employee=tomek, date_from=leave[0], date_to=leave[1], kind="urlop")
    point = ClockPoint.objects.create(workplace=firm, name="Wejście dla personelu", tag_token=team.token())
    kiosk = team.new_kiosk(people[0].user, firm.id, point.id)["kiosk_path"]
    tz = domain.zone(firm.timezone)  # last week's punches, recomputed into hours by the report
    for s in Shift.objects.filter(employee__workplace=firm, date__lt=today):
        begins, ends = domain.shift_span(s.date, s.start_time, s.end_time, tz)
        for kind, moment in (("in", begins - timedelta(minutes=4)), ("out", ends + timedelta(minutes=6))):
            if moment < timezone.now():
                Punch.objects.create(workplace=firm, employee=s.employee, kind=kind, at=moment, source="kiosk", point=point)
    return {"firm": firm, "accounts": accounts, "tag_path": f"/nfc/{point.tag_token}", "kiosk_path": kiosk}


# --- the visitor's sandbox ---------------------------------------------------------------------------------

def purge_expired():
    """Expired sandboxes go with their throwaway accounts (they were never a person's)."""
    for w in Workplace.objects.filter(demo_until__lt=timezone.now()):
        for account in team.erase_workplace(w):
            account.delete()


@transaction.atomic
def start(request):
    purge_expired()
    if settings.DEMO_MAX <= 0:
        raise DomainError("Demo jest wyłączone", 503)
    if Workplace.objects.filter(demo_until__gt=timezone.now()).count() >= settings.DEMO_MAX:
        raise DomainError("Demo jest teraz oblegane — spróbuj za kilka minut", 503)  # backpressure, not a queue
    made = build(prefix=f"demo-{secrets.token_hex(4)}-", demo_until=timezone.now() + timedelta(hours=settings.DEMO_HOURS))
    demo = {"firm": str(made["firm"].id), "tag": made["tag_path"], "kiosk": made["kiosk_path"],
            "logins": {role: made["accounts"][base].get_username() for role, base in SEEN_AS.items()}}
    enter(request, demo, "dyrektor")
    return info(request)


def enter(request, demo, role):
    sign_in(request, get_user_model().objects.get(username=demo["logins"][role]),
            backend="django.contrib.auth.backends.ModelBackend")
    request.session[SESSION_KEY] = demo  # login() as another user flushes the session: put it back


def current(request):
    demo = request.session.get(SESSION_KEY)
    if demo and Workplace.objects.filter(pk=demo["firm"], demo_until__gt=timezone.now()).exists():
        return demo
    return None


def switch(request, data):
    demo = current(request)
    if not demo:
        raise DomainError("Demo wygasło — zacznij nowe na stronie głównej", 404)
    role = domain.body_object(data).get("role")
    if role not in SEEN_AS:
        raise DomainError("Rola: dyrektor, kierownik albo pracownik")
    enter(request, demo, role)
    return info(request)


def info(request):
    demo = current(request)
    if not demo:
        return {"demo": None}
    w = Workplace.objects.get(pk=demo["firm"])
    me = request.user.get_username() if request.user.is_authenticated else None
    role = next((r for r, login in demo["logins"].items() if login == me), None)
    cards = [{"name": e.name, "card": e.card_uid} for e in w.employees.exclude(card_uid="").order_by("name")]
    return {"demo": {"workplace": demo["firm"], "until": w.demo_until.isoformat(), "role": role,
                     "tag": demo["tag"], "kiosk": demo["kiosk"], "cards": cards}}
