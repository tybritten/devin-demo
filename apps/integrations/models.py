import os
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel

ENV_VAR_NAME = RegexValidator(
    r"^[A-Z][A-Z0-9_]{0,99}$", "Use an environment variable name like CRM_CLIENT_SECRET."
)
GUID = RegexValidator(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    "Enter a GUID.",
)


class ExternalSystem(TimeStampedModel):
    """A system outside this app (Dataverse environment, SharePoint site) that apps use."""

    class Kind(models.TextChoices):
        DATAVERSE = "dataverse", "Dataverse"
        SHAREPOINT = "sharepoint", "SharePoint"

    class Access(models.TextChoices):
        READ_ONLY = "read_only", "Read-only"
        READ_WRITE = "read_write", "Read-write"

    # Bearer tokens are only ever sent to hosts under these suffixes.
    HOST_SUFFIXES = {
        Kind.DATAVERSE: (".dynamics.com",),
        Kind.SHAREPOINT: (".sharepoint.com",),
    }

    slug = models.SlugField(unique=True, help_text="Stable ID importers refer to, e.g. crm-prod.")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    access = models.CharField(
        max_length=20,
        choices=Access.choices,
        default=Access.READ_ONLY,
        help_text="Read-only systems refuse every write, whatever the code calling them does.",
    )
    base_url = models.URLField(
        "URL",
        help_text="Dataverse: environment URL, e.g. https://contoso.crm.dynamics.com. "
        "SharePoint: site URL, e.g. https://contoso.sharepoint.com/sites/ops.",
    )
    tenant_id = models.CharField("Entra tenant ID", max_length=36, validators=[GUID])
    client_id = models.CharField("Entra app (client) ID", max_length=36, validators=[GUID])
    client_secret_env = models.CharField(
        "client secret env var",
        max_length=100,
        validators=[ENV_VAR_NAME],
        help_text="Name of the environment variable holding the app's client secret "
        "(e.g. a Key Vault reference). The secret itself is never stored here.",
    )
    enabled = models.BooleanField(default=True)
    timeout_seconds = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(300)]
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("integrations:system_detail", args=[self.slug])

    @property
    def is_writable(self):
        return self.access == self.Access.READ_WRITE

    @property
    def secret_configured(self):
        return bool(os.environ.get(self.client_secret_env))

    def clean(self):
        parts = urlsplit(self.base_url or "")
        if parts.scheme != "https":
            raise ValidationError({"base_url": "Must be an https:// URL."})
        if parts.query or parts.fragment or parts.username or parts.port:
            raise ValidationError({"base_url": "Remove the query string, fragment, login or port."})
        suffixes = self.HOST_SUFFIXES.get(self.kind, ())
        if not (parts.hostname or "").lower().endswith(suffixes):
            raise ValidationError(
                {"base_url": f"{self.get_kind_display()} URLs must be on {', '.join(suffixes)}."}
            )
        if self.kind == self.Kind.DATAVERSE and parts.path.strip("/"):
            raise ValidationError({"base_url": "Use the environment's root URL, with no path."})


class SyncRun(models.Model):
    """One execution of an importer. Operational telemetry, so not copied into the audit log."""

    audit_skip = True

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIAL = "partial", "Completed with errors"
        FAILED = "failed", "Failed"

    system = models.ForeignKey(ExternalSystem, on_delete=models.PROTECT, related_name="runs")
    job = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    fetched = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    unchanged = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.job} @ {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration(self):
        return self.finished_at - self.started_at if self.finished_at else None
