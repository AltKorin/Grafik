from django.contrib import admin

from .models import LoginEvent, TermsAcceptance


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginEvent)
class LoginEventAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "kind", "username", "ip"]
    list_filter = ["kind"]
    search_fields = ["username", "ip"]


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "user", "version", "ip"]
    list_filter = ["version"]
