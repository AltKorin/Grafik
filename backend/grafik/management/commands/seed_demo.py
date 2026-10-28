"""Demo firm for local runs and E2E: `manage.py seed_demo [--reset]`. Prints logins and the NFC links
(the kiosk secret is shown only here, like in the panel). Idempotent: without --reset an existing demo stays."""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from grafik import domain, team
from grafik.models import ClockPoint, Department, Employee, Punch, Shift, Unavailability, Workplace

NAME = "Bistro Demo"
PEOPLE = [  # login, name, department, role, card
    ("dyrektor-demo", "Dorota Dyrektor", None, "dyrektor", ""),
    ("kuchnia-kier", "Kamil Kierownik", "Kuchnia", "kierownik", ""),
    ("anna", "Anna Nowak", "Kuchnia", "pracownik", "04A1B2C3"),
    ("tomek", "Tomasz Wiśniewski", "Kuchnia", "pracownik", "04D4E5F6"),
    ("ola", "Aleksandra Lewandowska", "Sala", "pracownik", "0477AA11"),
    (None, "Piotr Zieliński", "Sala", "pracownik", "0488BB22"),  # card only, no phone
]
HOURS = [("06:00", "14:00"), ("14:00", "22:00"), ("10:00", "18:00")]


class Command(BaseCommand):
    help = "Zakłada firmę demo z zespołem, grafikiem, odbiciami i punktem NFC."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="usuń demo i załóż od nowa (nowe linki)")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        password = os.environ.get("DEMO_PASSWORD") or "demo-haslo-do-testow"
        existing = Workplace.objects.filter(name=NAME).first()
        if existing and not reset:
            self.stdout.write(f"Demo już jest ({existing.id}). Nowe linki: --reset")
            return
        if existing:
            director = existing.employees.filter(role="dyrektor").first()
            team.delete_workplace(director.user, existing.id, {"confirm": NAME})
        User = get_user_model()
        firm = Workplace.objects.create(name=NAME)
        depts = {n: Department.objects.create(workplace=firm, name=n, color=c) for n, c in (("Kuchnia", "#c95a1e"), ("Sala", "#1e5f9b"))}
        people = []
        for login, name, dept, role, card in PEOPLE:
            user = None
            if login:
                user = User.objects.filter(username=login).first() or User.objects.create_user(login)
                user.set_password(password)
                user.is_active = True
                user.save()
            people.append(Employee.objects.create(workplace=firm, user=user, name=name, role=role,
                                                  department=depts.get(dept), card_uid=card))
        today = domain.local_today(firm.timezone)
        monday = domain.week_start(today)
        for i, e in enumerate(people[1:]):
            for d in range(-7, 7):
                day = monday + timedelta(days=d)
                if (d + i) % 7 in (5, 6):
                    continue
                start, end = HOURS[(i + (d // 7)) % len(HOURS)]
                Shift.objects.create(employee=e, date=day, start_time=start, end_time=end)
        tomek = people[3]
        Shift.objects.filter(employee=tomek, date__range=(monday + timedelta(days=9), monday + timedelta(days=11))).delete()
        Unavailability.objects.create(employee=tomek, date_from=monday + timedelta(days=9), date_to=monday + timedelta(days=11), kind="urlop")
        point = ClockPoint.objects.create(workplace=firm, name="Wejście dla personelu", tag_token=team.token())
        kiosk = team.new_kiosk(people[0].user, firm.id, point.id)["kiosk_path"]
        # last week's punches, recomputed into hours by the report
        tz = domain.zone(firm.timezone)
        for s in Shift.objects.filter(employee__workplace=firm, date__lt=today):
            begins, ends = domain.shift_span(s.date, s.start_time, s.end_time, tz)
            for kind, moment in (("in", begins - timedelta(minutes=4)), ("out", ends + timedelta(minutes=6))):
                if moment < timezone.now():
                    Punch.objects.create(workplace=firm, employee=s.employee, kind=kind, at=moment, source="kiosk", point=point)
        self.stdout.write(f"Firma: {NAME} ({firm.id})")
        self.stdout.write(f"Hasło kont demo: {'DEMO_PASSWORD z .env' if os.environ.get('DEMO_PASSWORD') else password}")
        for login, name, _, role, card in PEOPLE:
            self.stdout.write(f"  {login or '(bez logowania)':16} {name} — {role}{f', karta {card}' if card else ''}")
        self.stdout.write(f"Naklejka NFC: /nfc/{point.tag_token}")
        self.stdout.write(f"Kiosk:        {kiosk}")
