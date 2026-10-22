from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "actor_label",
        "action",
        "content_type",
        "object_repr",
        "ip_address",
    )
    list_filter = ("action", "content_type")
    search_fields = ("actor_label", "object_repr", "object_id", "request_id")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
