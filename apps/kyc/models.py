from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Customer(TimeStampedModel):
    class Type(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        BUSINESS = "business", "Business"

    customer_type = models.CharField(max_length=20, choices=Type.choices, default=Type.INDIVIDUAL)
    legal_name = models.CharField(max_length=255)
    external_ref = models.CharField(
        "External reference",
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="ID of this customer in the source system (CRM, core banking, etc).",
    )
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 code.")

    class Meta:
        ordering = ["legal_name"]

    def __str__(self):
        return self.legal_name


class ReviewCaseQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=ReviewCase.CLOSED_STATUSES)

    def closed(self):
        return self.filter(status__in=ReviewCase.CLOSED_STATUSES)

    def overdue(self):
        return self.open().filter(due_date__lt=timezone.localdate())


class ReviewCase(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_REVIEW = "in_review", "In review"
        PENDING_INFO = "pending_info", "Pending info"
        ESCALATED = "escalated", "Escalated"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class ReviewType(models.TextChoices):
        ONBOARDING = "onboarding", "Onboarding"
        PERIODIC = "periodic", "Periodic refresh"
        TRIGGER = "trigger", "Trigger event"

    class Risk(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    CLOSED_STATUSES = (Status.APPROVED, Status.REJECTED)

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="cases")
    review_type = models.CharField(
        max_length=20, choices=ReviewType.choices, default=ReviewType.ONBOARDING
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    risk_rating = models.CharField(max_length=10, choices=Risk.choices, default=Risk.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True, help_text="Why this review was opened.")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_kyc_cases",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_kyc_cases",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_kyc_cases",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    objects = ReviewCaseQuerySet.as_manager()

    class Meta:
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["assigned_to", "status"]),
        ]
        permissions = [
            ("decide_case", "Can approve or reject KYC cases"),
            ("approve_high_risk", "Can approve high-risk KYC cases"),
        ]

    def __str__(self):
        return f"{self.reference} · {self.customer}"

    def get_absolute_url(self):
        return reverse("kyc:case_detail", args=[self.pk])

    @property
    def reference(self):
        return f"KYC-{self.pk:06d}" if self.pk else "KYC-NEW"

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES

    @property
    def is_overdue(self):
        return self.is_open and self.due_date is not None and self.due_date < timezone.localdate()


class CaseDocument(TimeStampedModel):
    class DocumentType(models.TextChoices):
        PASSPORT = "passport", "Passport"
        DRIVERS_LICENSE = "drivers_license", "Driver's license"
        NATIONAL_ID = "national_id", "National ID"
        PROOF_OF_ADDRESS = "proof_of_address", "Proof of address"
        COMPANY_REGISTRATION = "company_registration", "Company registration"
        OTHER = "other", "Other"

    case = models.ForeignKey(ReviewCase, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to="kyc/%Y/%m/")
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} · {self.original_name}"


class CaseEvent(models.Model):
    """Append-only audit trail for a case. Every state change and comment is recorded here."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        ASSIGNED = "assigned", "Assigned"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENT = "comment", "Comment"
        DOCUMENT_ADDED = "document_added", "Document added"

    case = models.ForeignKey(ReviewCase, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    from_status = models.CharField(max_length=20, choices=ReviewCase.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=ReviewCase.Status.choices, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.case.reference} {self.get_kind_display()}"
