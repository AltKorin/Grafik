import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords


class Workplace(models.Model):
    """Firma — hotel, restauracja, sklep: one schedule, one set of people."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64, default="Europe/Warsaw")
    created_at = models.DateTimeField(auto_now_add=True)
    # A visitor's sandbox from „Wypróbuj demo” (grafik.demo): erased after this moment. Empty = a real firm.
    demo_until = models.DateTimeField(null=True, blank=True, db_index=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name


class Department(models.Model):
    """Dział — kuchnia, recepcja, sprzątanie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#5b7a8c")
    history = HistoricalRecords()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workplace", "name"], name="unique_department_name")]

    def __str__(self):
        return self.name


class Employee(models.Model):
    """Pracownik. The login account is optional: someone who only taps a card at the kiosk needs none."""

    ROLES = [("dyrektor", "Dyrektor"), ("kierownik", "Kierownik działu"), ("pracownik", "Pracownik")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE, related_name="employees")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employments")
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    role = models.CharField(max_length=10, choices=ROLES, default="pracownik")
    # Serial number (UID) of the NFC card or key fob, as the reader types it.
    card_uid = models.CharField(max_length=64, blank=True)
    active = models.BooleanField(default=True)
    # Invitation link (/zaproszenie/<token>): only the sha256 of the token is kept; one use, then cleared.
    invite_hash = models.CharField(max_length=64, blank=True, db_index=True)
    invite_expires = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workplace", "user"], condition=Q(user__isnull=False), name="unique_employee_user"),
            models.UniqueConstraint(fields=["workplace", "card_uid"], condition=~Q(card_uid=""), name="unique_employee_card"),
        ]

    def __str__(self):
        return self.name


class Shift(models.Model):
    """Zmiana — local date and wall-clock times; end ≤ start means it ends the next day."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="shifts")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    notes = models.CharField(max_length=200, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["date", "start_time"]


class Unavailability(models.Model):
    """Niedyspozycyjność — visible at once, no approval. History proves it was reported (PLAN.md §3)."""

    KINDS = [("urlop", "Urlop"), ("l4", "L4"), ("inne", "Niedostępność")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="unavailabilities")
    date_from = models.DateField()
    date_to = models.DateField()
    kind = models.CharField(max_length=6, choices=KINDS, default="inne")
    note = models.CharField(max_length=200, blank=True)
    history = HistoricalRecords()


class ChangeRequest(models.Model):
    """Wniosek o zmianę grafiku; the manager's approval applies it in the same transaction."""

    KINDS = [("swap", "Zamiana"), ("cancel", "Odwołanie zmiany"), ("modify", "Zmiana godzin"), ("add", "Dodatkowa zmiana")]
    STATUSES = [("pending", "Czeka"), ("approved", "Przyjęty"), ("rejected", "Odrzucony"), ("withdrawn", "Wycofany")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="requests")
    kind = models.CharField(max_length=6, choices=KINDS)
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    swap_shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    new_date = models.DateField(null=True, blank=True)
    new_start = models.TimeField(null=True, blank=True)
    new_end = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=9, choices=STATUSES, default="pending")
    reviewed_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]


class ClockPoint(models.Model):
    """Punkt odbić — an entrance with an NFC sticker (phones) and optionally a kiosk tablet (cards)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE, related_name="clock_points")
    name = models.CharField(max_length=120)
    # Written on the sticker as a URL. Readable by anyone who taps it, so it never authorizes a kiosk.
    tag_token = models.CharField(max_length=43, unique=True)
    # sha256 of the kiosk link's secret; empty = no kiosk at this point. The link is shown once.
    kiosk_hash = models.CharField(max_length=64, blank=True, db_index=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.name


class Punch(models.Model):
    """Odbicie — append-only event. A correction is a new row (manual punch, or `void` of a wrong one);
    the hours are always recomputed from the events (CLAUDE.md: event sourcing)."""

    KINDS = [("in", "Wejście"), ("out", "Wyjście"), ("void", "Anulowanie odbicia")]
    SOURCES = [("tag", "Telefon przy naklejce NFC"), ("kiosk", "Karta w kiosku"), ("manual", "Wpis kierownika")]

    workplace = models.ForeignKey(Workplace, on_delete=models.CASCADE, related_name="punches")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="punches")
    kind = models.CharField(max_length=4, choices=KINDS)
    at = models.DateTimeField()
    source = models.CharField(max_length=6, choices=SOURCES)
    point = models.ForeignKey(ClockPoint, on_delete=models.SET_NULL, null=True, blank=True)
    voids = models.OneToOneField("self", on_delete=models.CASCADE, null=True, blank=True, related_name="voided_by")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "pk"]
        indexes = [models.Index(fields=["employee", "at"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Punch is immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Punch is immutable")
