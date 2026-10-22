from django.contrib import admin, messages

from .models import ApiClient, FeatureFlag, FlagChange


class FlagChangeInline(admin.TabularInline):
    model = FlagChange
    extra = 0
    can_delete = False
    fields = ["created_at", "action", "actor", "changes", "comment"]
    readonly_fields = fields

    class Media:
        css = {"all": ["kyc/admin.css"]}

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """Read-only: flags are edited in the Feature Flags app so every change is recorded."""

    list_display = ["key", "name", "enabled", "rollout_percentage", "is_archived", "updated_at"]
    list_filter = ["enabled", "is_archived"]
    search_fields = ["key", "name"]
    inlines = [FlagChangeInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApiClient)
class ApiClientAdmin(admin.ModelAdmin):
    list_display = ["name", "token_prefix", "is_active", "last_used_at", "created_at"]
    fields = ["name", "is_active", "token_prefix", "last_used_at"]
    readonly_fields = ["token_prefix", "last_used_at"]

    def save_model(self, request, obj, form, change):
        raw = obj.set_new_token() if not change else None
        super().save_model(request, obj, form, change)
        if raw:
            messages.warning(
                request,
                f"Token for {obj.name} (shown once, store it now): {raw}",
            )

    def has_delete_permission(self, request, obj=None):
        return False
