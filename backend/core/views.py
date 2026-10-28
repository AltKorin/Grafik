from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.middleware.csrf import CsrfViewMiddleware, get_token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import accounts
from .domain_errors import DomainError
from .i18n import error_body, is_english, tr


class PostThrottle(SimpleRateThrottle):
    """Per-IP limit on POSTs only, so reading the form state is never throttled."""

    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginThrottle(PostThrottle):
    scope = "login"


class RegistrationThrottle(PostThrottle):
    scope = "registration"


def csrf_denied(request):
    # SessionAuthentication does not enforce CSRF for anonymous requests.
    return CsrfViewMiddleware(lambda r: None).process_view(request._request, lambda r: None, (), {})


def me(request):
    return {
        "user": request.user.username if request.user.is_authenticated else None,
        "csrf": get_token(request),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    with connection.cursor() as c:
        c.execute("SELECT 1")
    return Response({"status": "ok"})


@api_view(["GET", "POST", "DELETE"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def session(request):
    if request.method == "DELETE":
        logout(request)
        return Response({"user": None})
    if request.method == "POST":
        if not isinstance(request.data, dict):
            return Response({"error": tr("Oczekiwano obiektu JSON")}, status=400)
        if csrf_denied(request):
            return Response({"error": tr("Błąd weryfikacji CSRF")}, status=403)
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        if (
            not isinstance(username, str)
            or not isinstance(password, str)
            or len(username) > 150
            or len(password) > 4096
        ):
            return Response({"error": tr("Nieprawidłowe pola logowania")}, status=400)
        if "@" in username:  # self-registered accounts log in with their e-mail, stored lower-case
            username = username.strip().lower()
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"error": tr("Nieprawidłowy login lub hasło")}, status=400)
        login(request, user)
    return Response(me(request))


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    if csrf_denied(request):
        return Response({"error": tr("Błąd weryfikacji CSRF")}, status=403)
    try:
        user, firm = accounts.register(request, request.data)
    except DomainError as error:
        return Response(error_body(error), status=error.status)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return Response({**me(request), "workplace": str(firm.id)}, status=201)


@api_view(["POST"])
@throttle_classes([LoginThrottle])  # the current password must not be guessable here either
def password(request):
    try:
        return Response(accounts.change_password(request, request.data))
    except DomainError as error:
        return Response(error_body(error), status=error.status)


@api_view(["GET"])
@permission_classes([AllowAny])
def terms(request):
    current = accounts.terms()
    # The Polish text is the binding one (its hash is what acceptance records); English is a courtesy translation.
    html = accounts.TERMS_EN_FILE.read_text(encoding="utf-8") if is_english() else current["html"]
    return Response({"version": current["version"], "html": html})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_config(request):
    # Empty id = no analytics tag at all (CLAUDE.md: feature flag, switched on per deployment).
    return Response({"ga_measurement_id": settings.GA_MEASUREMENT_ID})
