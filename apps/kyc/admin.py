from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import CaseDocument, CaseEvent, Customer, ReviewCase


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["legal_name", "customer_type", "external_ref", "country", "created_at"]
    list_filter = ["customer_type", "country"]
    search_fields = ["legal_name", "external_ref", "email"]


class AuditInline(admin.TabularInline):
    extra = 0
    can_delete = False

    class Media:
        css = {"all": ["kyc/admin.css"]}

    def has_add_permission(self, request, obj=None):
        return False


class CaseDocumentInline(AuditInline):
    model = CaseDocument
    fields = ["document_type", "download", "uploaded_by", "created_at"]
    readonly_fields = fields

    @admin.display(description="File")
    def download(self, obj):
        # Media is never served directly; link to the permission-checked view.
        return format_html(
            '<a href="{}">{}</a>',
            reverse("kyc:document_download", args=[obj.pk]),
            obj.original_name,
        )


class CaseEventInline(AuditInline):
    model = CaseEvent
    fields = ["created_at", "kind", "actor", "from_status", "to_status", "message"]
    readonly_fields = fields


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
