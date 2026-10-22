from django.contrib import admin

from .models import __Model__, __Model__Event


class EventInline(admin.TabularInline):
    model = __Model__Event
    extra = 0
    can_delete = False
    fields = ["created_at", "kind", "actor", "from_status", "to_status", "message"]
    readonly_fields = fields

    class Media:
        css = {"all": ["kyc/admin.css"]}

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(__Model__)
class __Model__Admin(admin.ModelAdmin):
    """Read-only: records change only via `services`, so every change is audited."""

    list_display = ["title", "status", "owner", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "description"]
    inlines = [EventInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
