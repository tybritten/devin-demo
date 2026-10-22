from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class RefundQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=Refund.CLOSED_STATUSES)

    def closed(self):
        return self.filter(status__in=Refund.CLOSED_STATUSES)

    def pending(self):
        return self.filter(status=Refund.Status.REQUESTED)

    def awaiting_payment(self):
        return self.filter(status=Refund.Status.APPROVED)


class Refund(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class Reason(models.TextChoices):
        DUPLICATE_CHARGE = "duplicate_charge", "Duplicate charge"
        BILLING_ERROR = "billing_error", "Billing error"
        PRODUCT_ISSUE = "product_issue", "Product issue"
        SERVICE_ISSUE = "service_issue", "Service issue"
        FRAUD = "fraud", "Fraud / unauthorized"
        GOODWILL = "goodwill", "Goodwill"
        OTHER = "other", "Other"

    CLOSED_STATUSES = (Status.PAID, Status.REJECTED, Status.CANCELLED)

    customer_name = models.CharField(max_length=255)
    customer_ref = models.CharField(
        "Customer reference", max_length=100, blank=True, help_text="Customer ID in the CRM."
    )
    order_ref = models.CharField(
        "Order / transaction", max_length=100, blank=True, help_text="Order, invoice or charge ID."
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)

    objects = RefundQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        permissions = [
            ("approve_refund", "Can approve or reject refunds"),
            ("approve_over_limit", "Can approve refunds above the approval limit"),
            ("mark_paid", "Can mark approved refunds as paid"),
        ]

    def __str__(self):
        return f"{self.reference} · {self.customer_name}"

    def get_absolute_url(self):
        return reverse("refunds:refund_detail", args=[self.pk])

    @property
    def reference(self):
        return f"RF-{self.pk:06d}" if self.pk else "RF-NEW"

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES

    @property
    def over_limit(self):
        return self.amount > settings.REFUND_APPROVAL_LIMIT


class RefundEvent(models.Model):
    """Append-only audit trail for a refund."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENT = "comment", "Comment"

    refund = models.ForeignKey(Refund, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    from_status = models.CharField(max_length=20, choices=Refund.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Refund.Status.choices, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.refund.reference} {self.get_kind_display()}"
