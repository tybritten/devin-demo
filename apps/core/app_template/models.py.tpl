from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel


class __Model__QuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=__Model__.CLOSED_STATUSES)


class __Model__(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    CLOSED_STATUSES = (Status.DONE, Status.CANCELLED)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    objects = __Model__QuerySet.as_manager()

    class Meta:
        verbose_name = "__model_title__"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("__app__:detail", args=[self.pk])

    @property
    def is_open(self):
        return self.status not in self.CLOSED_STATUSES


class __Model__Event(models.Model):
    """Append-only audit trail. Only `services.py` writes these."""

    class Kind(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENT = "comment", "Comment"

    record = models.ForeignKey(__Model__, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    from_status = models.CharField(max_length=20, choices=__Model__.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=__Model__.Status.choices, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.record} {self.get_kind_display()}"
