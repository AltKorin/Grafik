from django.conf import settings
from django.db import models


class LoginEvent(models.Model):
    """Append-only record of logins, logouts and failed attempts.

    RODO — czynność „bezpieczeństwo kont”:
    · dane: login, IP, przeglądarka (user-agent), czas
    · cel: wykrywanie włamań i prób zgadywania haseł, odpowiedź „kto się logował”
    · podstawa: art. 6 ust. 1 lit. f (uzasadniony interes — bezpieczeństwo usługi)
    · retencja: RETENCJA_LOGIN_DNI (domyślnie 365) — komenda `retencja_danych` w cronie;
      przy usunięciu firmy IP i user-agent kont bez innych firm są czyszczone od razu
    · dostęp: tylko my (admin serwisowy)
    """

    KINDS = [("login", "Logowanie"), ("logout", "Wylogowanie"), ("failed", "Nieudana próba")]

    kind = models.CharField(max_length=8, choices=KINDS)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Failed attempts keep the typed username even when no such user exists (brute-force trail).
    username = models.CharField(max_length=150, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("LoginEvent is immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("LoginEvent is immutable")


class TermsAcceptance(models.Model):
    """Insert-only proof of which regulamin text an account accepted at registration.

    Not a consent (art. 6 ust. 1 lit. a): the account is needed to perform the contract (lit. b);
    this row proves the person was shown the terms and the privacy policy (art. 13).
    · dane: konto, wersja i skrót sha256 treści regulaminu, IP, czas
    · retencja: przez czas umowy + przedawnienie roszczeń; konto usunięte → user NULL, IP czyszczone
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    version = models.CharField(max_length=20)
    sha256 = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("TermsAcceptance is immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("TermsAcceptance is immutable")
