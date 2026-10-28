"""Demo firm for local runs and E2E: `manage.py seed_demo [--reset]`. Prints logins and the NFC links
(the kiosk secret is shown only here, like in the panel). Idempotent: without --reset an existing demo stays."""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grafik import demo, team
from grafik.demo import NAME, PEOPLE
from grafik.models import Workplace


class Command(BaseCommand):
    help = "Zakłada firmę demo z zespołem, grafikiem, odbiciami i punktem NFC."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="usuń demo i załóż od nowa (nowe linki)")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        password = os.environ.get("DEMO_PASSWORD")
        if not password and not settings.DEBUG:
            # the fallback is in a public repository: on a real server it would be an open door
            raise CommandError("Ustaw DEMO_PASSWORD w .env (długie, losowe) — bez niego demo działa tylko lokalnie (DEBUG=1)")
        password = password or "demo-haslo-do-testow"
        existing = Workplace.objects.filter(name=NAME, demo_until__isnull=True).first()
        if existing and not reset:
            self.stdout.write(f"Demo już jest ({existing.id}). Nowe linki: --reset")
            return
        if existing:
            director = existing.employees.filter(role="dyrektor").first()
            team.delete_workplace(director.user, existing.id, {"confirm": NAME})
        made = demo.build(password=password)
        firm = made["firm"]
        self.stdout.write(f"Firma: {NAME} ({firm.id})")
        self.stdout.write(f"Hasło kont demo: {'DEMO_PASSWORD z .env' if os.environ.get('DEMO_PASSWORD') else password}")
        for login, name, _, role, card in PEOPLE:
            self.stdout.write(f"  {login or '(bez logowania)':16} {name} — {role}{f', karta {card}' if card else ''}")
        self.stdout.write(f"Naklejka NFC: {made['tag_path']}")
        self.stdout.write(f"Kiosk:        {made['kiosk_path']}")
