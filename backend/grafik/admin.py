"""Service panel for us (CLAUDE.md: jazzmin is our tool, the client works in /panel)."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from core.admin import ReadOnlyAdmin

from .models import ChangeRequest, ClockPoint, Department, Employee, Punch, Shift, Unavailability, Workplace


@admin.register(Workplace)
class WorkplaceAdmin(SimpleHistoryAdmin):
    list_display = ["name", "timezone", "created_at"]
    search_fields = ["name"]


@admin.register(Employee)
class EmployeeAdmin(SimpleHistoryAdmin):
    list_display = ["name", "workplace", "department", "role", "active"]
    list_filter = ["role", "active"]
    search_fields = ["name", "user__username"]


@admin.register(Department, Shift, Unavailability, ChangeRequest, ClockPoint)
class HistoryAdmin(SimpleHistoryAdmin):
    pass


@admin.register(Punch)
class PunchAdmin(ReadOnlyAdmin):
    list_display = ["at", "employee", "kind", "source", "point"]
    list_filter = ["kind", "source"]
