from django.contrib import admin

from .models import Refund, RefundEvent


class RefundEventInline(admin.TabularInline):
    model = RefundEvent
    extra = 0
    can_delete = False
    fields = ["created_at", "kind", "actor", "from_status", "to_status", "message"]
    readonly_fields = fields

    class Media:
        css = {"all": ["kyc/admin.css"]}

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Read-only: refunds change only via `apps.refunds.services`, so every change is audited."""

    list_display = ["reference", "customer_name", "amount", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]
    search_fields = ["customer_name", "customer_ref", "order_ref"]
    inlines = [RefundEventInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
