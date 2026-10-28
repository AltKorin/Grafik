"""Self-service accounts: registration of a new firm, own password, the regulamin.

RODO — czynność „konto w Grafiku” (django.contrib.auth.User):
· dane: e-mail lub login nadany przez dyrektora, hasło (skrót), data ostatniego logowania
· cel: logowanie do panelu firmy i odbicia z telefonu; kontakt w sprawie usługi
· podstawa: art. 6 ust. 1 lit. b (umowa — regulamin); dane pracowników firma powierza nam
  (art. 28) — firma jest ich administratorem, my przetwarzamy je w jej imieniu
· retencja: do usunięcia firmy przez klienta; wtedy konta bez innych firm są anonimizowane
  (`grafik.team.delete_workplace`)
· dostęp: dyrektor firmy (lista pracowników), my (admin serwisowy)
"""

import hashlib
import re
from functools import cache
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from .domain_errors import DomainError
from .models import TermsAcceptance
from .signals import client_ip

TERMS_FILE = Path(__file__).resolve().parent.parent / "grafik" / "data" / "regulamin.html"
TERMS_EN_FILE = TERMS_FILE.with_name("regulamin.en.html")


@cache
def terms():
    """One source: the file. Version from its first-line comment, hash over the exact bytes served."""
    raw = TERMS_FILE.read_bytes()
    version = re.search(rb"wersja: ([\d-]+)", raw).group(1).decode()
    return {"version": version, "sha256": hashlib.sha256(raw).hexdigest(), "html": raw.decode()}


def password_errors(password, user):
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise DomainError(" ".join(error.messages)) from None


def text(data, key, limit):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > limit:
        raise DomainError("Nieprawidłowe pola formularza")
    return value


@transaction.atomic
def register(request, data):
    """New account + new firm; the person becomes its director. Returns the user, not logged in yet."""
    if not isinstance(data, dict):
        raise DomainError("Oczekiwano obiektu JSON")
    if text(data, "website", 200):  # honeypot: people never see this field
        raise DomainError("Nie udało się założyć konta")
    email = text(data, "email", 150).strip().lower()
    password = text(data, "password", 4096)
    firm_name = text(data, "firm", 200).strip()
    person = text(data, "name", 120).strip()
    try:
        validate_email(email)
    except ValidationError:
        raise DomainError("Podaj poprawny adres e-mail") from None
    if not firm_name:
        raise DomainError("Podaj nazwę firmy")
    if not person:
        raise DomainError("Podaj swoje imię i nazwisko")
    if data.get("accept") is not True:
        raise DomainError("Zaakceptuj regulamin, żeby założyć konto")
    User = get_user_model()
    if User.objects.filter(username__iexact=email).exists():
        raise DomainError("Konto z tym adresem już istnieje — zaloguj się", 409)
    password_errors(password, User(username=email, email=email))
    try:
        with transaction.atomic():
            user = User.objects.create_user(email, email=email, password=password)
    except IntegrityError:  # two submits of the same form at once
        raise DomainError("Konto z tym adresem już istnieje — zaloguj się", 409) from None
    return user, found_firm(request, user, firm_name, person)


def found_firm(request, user, firm_name, person):
    """The account becomes director of a new firm and accepts the current regulamin."""
    from grafik.models import Employee, Workplace

    firm = Workplace.objects.create(name=firm_name)
    Employee.objects.create(workplace=firm, user=user, name=person, role="dyrektor")
    current = terms()
    TermsAcceptance.objects.create(user=user, version=current["version"], sha256=current["sha256"], ip=client_ip(request))
    return firm


@transaction.atomic
def add_firm(request, data):
    """A logged-in account founds another firm (or its first one, e.g. our service admin)."""
    from grafik.models import Employee

    if not isinstance(data, dict):
        raise DomainError("Oczekiwano obiektu JSON")
    firm_name = text(data, "firm", 200).strip()
    person = text(data, "name", 120).strip()
    if not firm_name:
        raise DomainError("Podaj nazwę firmy")
    if not person:
        raise DomainError("Podaj swoje imię i nazwisko")
    if data.get("accept") is not True:
        raise DomainError("Zaakceptuj regulamin, żeby założyć firmę")
    user = get_user_model().objects.select_for_update().get(pk=request.user.pk)  # two submits at once count once
    if Employee.objects.filter(user=user, workplace__demo_until__isnull=False).exists():
        raise DomainError("W demo nie zakłada się firm — załóż własne konto na stronie głównej", 403)
    if Employee.objects.filter(user=user, role="dyrektor").count() >= settings.MAX_FIRMS_PER_ACCOUNT:
        raise DomainError("Jedno konto może prowadzić najwyżej {limit} firm", 409, limit=settings.MAX_FIRMS_PER_ACCOUNT)
    return found_firm(request, user, firm_name, person)


def change_password(request, data):
    if not isinstance(data, dict):
        raise DomainError("Oczekiwano obiektu JSON")
    user = request.user
    if not user.check_password(text(data, "current", 4096)):
        raise DomainError("Obecne hasło się nie zgadza")
    new = text(data, "new", 4096)
    password_errors(new, user)
    user.set_password(new)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)  # stay logged in here, other sessions end
    return {"changed": True}
