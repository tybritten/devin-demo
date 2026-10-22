from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from . import users

User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class OpsUserAdmin(UserAdmin):
    actions = ["deactivate_users", "reactivate_users"]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Deactivate selected users", permissions=["change"])
    def deactivate_users(self, request, queryset):
        count = users.deactivate(queryset)
        self.message_user(request, f"Deactivated {count} user(s).", messages.SUCCESS)

    @admin.action(description="Reactivate selected users", permissions=["change"])
    def reactivate_users(self, request, queryset):
        count = users.reactivate(queryset)
        self.message_user(request, f"Reactivated {count} user(s).", messages.SUCCESS)
