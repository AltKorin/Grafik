"""Hak core_sso (SSO_PO_ZALOGOWANIU): role w Grafiku z Konta sudomie.

Prawa (core/test_sso.py):
- firma z Konta = Workplace o tym samym uuid; firmy, których Grafik nie zna (albo demo), pomijamy,
- osoba z dostępem dostaje Employee (pierwsze logowanie) albo aktualną rolę (każde kolejne),
- w firmie zarządzanej przez Konto (w_koncie) odebrany dostęp = Employee nieaktywny (Grafik go już nie wpuści),
- firm spoza Konta (w_koncie=False) nie ruszamy — tam dostęp nadaje dyrektor w Grafiku jak dawniej,
- nie reaktywujemy osoby wyłączonej w Grafiku (dyrektor ją zwolnił) — Konto nadaje dostęp, nie zatrudnienie.
"""
from grafik.models import Employee, Workplace

ROLE = {r for r, _ in Employee.ROLES}


def role_z_konta(user, firmy):
    z_konta = {f["id"]: f["rola"] for f in firmy if f["rola"] in ROLE}
    for w in Workplace.objects.filter(id__in=list(z_konta), demo_until__isnull=True):
        rola = z_konta[str(w.id)]
        e = Employee.objects.filter(workplace=w, user=user).first()
        if e is None:
            Employee.objects.create(workplace=w, user=user, name=user.first_name or user.username, role=rola)
        elif e.role != rola:
            e.role = rola
            e.save(update_fields=["role"])
    for e in Employee.objects.filter(user=user, active=True, workplace__w_koncie=True).exclude(workplace_id__in=list(z_konta)):
        e.active = False
        e.save(update_fields=["active"])
