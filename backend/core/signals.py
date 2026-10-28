from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import LoginEvent


def client_ip(request):
    # Caddy overwrites X-Forwarded-For with the real client IP, so the first entry is trusted.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None
    from django.core.validators import validate_ipv46_address
    from django.core.exceptions import ValidationError

    try:
        validate_ipv46_address(ip)
    except ValidationError:
        return None
    return ip


def record(kind, request, user=None, username=""):
    LoginEvent.objects.create(
        kind=kind,
        user=user,
        username=(username or (user.get_username() if user else ""))[:150],
        ip=client_ip(request) if request else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:300],
    )


@receiver(user_logged_in)
def logged_in(sender, request, user, **kwargs):
    record("login", request, user)


@receiver(user_logged_out)
def logged_out(sender, request, user, **kwargs):
    record("logout", request, user)


@receiver(user_login_failed)
def login_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "")
    record("failed", request, username=username if isinstance(username, str) else "")
