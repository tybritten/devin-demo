from django.contrib import admin

from .models import ExternalSystem, SyncRun


@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "kind", "access", "enabled", "secret_configured")
    list_filter = ("kind", "access", "enabled")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("secret_configured", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "kind", "access", "enabled", "base_url")}),
        (
            "Entra app credentials",
            {"fields": ("tenant_id", "client_id", "client_secret_env", "secret_configured")},
        ),
        (None, {"fields": ("timeout_seconds", "notes", "created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Secret set in environment")
    def secret_configured(self, obj):
        return obj.secret_configured

    def has_delete_permission(self, request, obj=None):
        return False  # disable instead, so sync history and audit references stay meaningful


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "system",
        "status",
        "started_at",
        "fetched",
        "created",
        "updated",
        "failed",
    )
    list_filter = ("status", "system", "job")
    date_hierarchy = "started_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
