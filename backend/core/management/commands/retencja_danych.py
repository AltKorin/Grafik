"""RODO retention as code, run daily from cron. Periods come from settings (env), not from here."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import LoginEvent


class Command(BaseCommand):
    help = "Usuwa dane po okresie retencji (log logowań starszy niż RETENCJA_LOGIN_DNI)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="tylko policz, nic nie usuwaj")

    def handle(self, *args, dry_run=False, **options):
        cutoff = timezone.now() - timedelta(days=settings.RETENCJA_LOGIN_DNI)
        old = LoginEvent.objects.filter(created_at__lt=cutoff)
        count = old.count()
        if not dry_run:
            old.delete()  # queryset delete never calls model.delete(), which forbids single deletes
        verb = "do usunięcia" if dry_run else "usunięto"
        self.stdout.write(f"LoginEvent starsze niż {settings.RETENCJA_LOGIN_DNI} dni: {count} {verb}")
