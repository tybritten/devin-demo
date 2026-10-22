from django.contrib import admin

from .models import CaseDocument, CaseEvent, Customer, ReviewCase


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["legal_name", "customer_type", "external_ref", "country", "created_at"]
    list_filter = ["customer_type", "country"]
    search_fields = ["legal_name", "external_ref", "email"]


class CaseDocumentInline(admin.TabularInline):
    model = CaseDocument
    extra = 0
    can_delete = False
    fields = ["document_type", "original_name", "file", "uploaded_by", "created_at"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class CaseEventInline(admin.TabularInline):
    model = CaseEvent
    extra = 0
    fields = ["created_at", "kind", "actor", "from_status", "to_status", "message"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ReviewCase)
class ReviewCaseAdmin(admin.ModelAdmin):
    list_display = ["reference", "customer", "status", "risk_rating", "assigned_to", "due_date"]
    list_filter = ["status", "risk_rating", "review_type"]
    search_fields = ["customer__legal_name", "customer__external_ref"]
    list_select_related = ["customer", "assigned_to"]
    readonly_fields = [
        "customer",
        "status",
        "assigned_to",
        "created_by",
        "decided_by",
        "decided_at",
        "created_at",
        "updated_at",
    ]
    inlines = [CaseDocumentInline, CaseEventInline]

    # Creation, assignment and status changes go through apps.kyc.services so they are audited.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ["case", "kind", "actor", "from_status", "to_status", "created_at"]
    list_filter = ["kind"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
