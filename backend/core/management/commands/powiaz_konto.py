"""Wiąże istniejące konto Grafiku z kontem w Koncie sudomie (migracja, OpenProject #770) i oznacza firmę jako
zarządzaną przez Konto. Bez zakładania nowego konta: dane, grafik i odbicia zostają przy dotychczasowym.

  python manage.py powiaz_konto biuro@przystanekwielbark.pl 2 --firma d8c0be9a-…
Idempotentne. sub zajęty przez inne konto = błąd (nic nie przepina).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core_sso.uslugi import powiaz
from grafik.models import Workplace


class Command(BaseCommand):
    help = "Powiąż konto Grafiku z kontem sudomie (sub z Konta)."

    def add_arguments(self, parser):
        parser.add_argument("login")
        parser.add_argument("sub", help="id konta w Koncie sudomie (claim sub)")
        parser.add_argument("--firma", help="uuid firmy (Workplace) do oznaczenia jako zarządzanej przez Konto")
        parser.add_argument("--issuer", default="", help="domyślnie OIDC_ISSUER z ustawień")

    def handle(self, login, sub, firma=None, issuer="", **opts):
        issuer = issuer or settings.OIDC_ISSUER
        if not issuer:
            raise CommandError("Brak OIDC_ISSUER — podaj --issuer albo ustaw w .env.")
        user = get_user_model().objects.filter(username=login.strip().lower()).first() or \
            get_user_model().objects.filter(username=login.strip()).first()
        if not user:
            raise CommandError(f"Nie ma konta „{login}”.")
        try:
            t = powiaz(user, issuer, sub)
        except ValueError as e:
            raise CommandError(str(e))
        self.stdout.write(f"Powiązano: {user.username} ← {t.issuer} #{t.sub}")
        if firma:
            n = Workplace.objects.filter(id=firma).update(w_koncie=True)
            if not n:
                raise CommandError(f"Nie ma firmy {firma}.")
            self.stdout.write(f"Firma {firma}: dostępami zarządza Konto sudomie.")
