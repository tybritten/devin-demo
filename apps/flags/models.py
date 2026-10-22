import hashlib
import secrets

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel

key_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9_.-]*$", "Use lowercase letters, numbers, dots, dashes and underscores."
)


def rollout_bucket(key, target):
    """Stable 0-99 bucket for `target` on flag `key`. Clients evaluating locally must match this."""
    digest = hashlib.sha256(f"{key}:{target}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


class FeatureFlag(TimeStampedModel):
    key = models.CharField(
        max_length=100,
        unique=True,
        validators=[key_validator],
        help_text="Identifier used in code, e.g. <code>checkout.new_flow</code>. Can't be changed.",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(
        default=False, help_text="Master switch. When off, the flag is off for everyone."
    )
    rollout_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        help_text="Share of targets (users, customers, ...) that get the flag when it is on.",
    )
    targets = ArrayField(
        models.CharField(max_length=200),
        default=list,
        blank=True,
        help_text="Target IDs that always get the flag when it is on, regardless of rollout.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key

    def get_absolute_url(self):
        return reverse("flags:flag_detail", args=[self.pk])

    def is_enabled_for(self, target=None):
        if not self.enabled or self.is_archived:
            return False
        if self.rollout_percentage >= 100:
            return True
        if target is None or target == "":
            return False
        target = str(target)
        return target in self.targets or rollout_bucket(self.key, target) < self.rollout_percentage

    @property
    def state(self):
        if self.is_archived:
            return "archived"
        if not self.enabled:
            return "off"
        if self.rollout_percentage >= 100:
            return "on"
        return "partial"


class FlagChange(models.Model):
    """Append-only history of flag changes. `changes` maps field -> [old, new]."""

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        ARCHIVED = "archived", "Archived"
        RESTORED = "restored", "Restored"

    flag = models.ForeignKey(FeatureFlag, on_delete=models.PROTECT, related_name="changes")
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    changes = models.JSONField(default=dict, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.flag.key} {self.get_action_display()}"


def _hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiClient(TimeStampedModel):
    """A service allowed to read flags over the API. Only a hash of its token is stored."""

    name = models.CharField(max_length=100, unique=True)
    token_prefix = models.CharField(max_length=8, editable=False)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "API client"

    def __str__(self):
        return self.name

    def set_new_token(self):
        raw = secrets.token_urlsafe(32)
        self.token_prefix = raw[:8]
        self.token_hash = _hash_token(raw)
        return raw

    @classmethod
    def authenticate(cls, raw):
        if not raw:
            return None
        client = cls.objects.filter(token_hash=_hash_token(raw), is_active=True).first()
        if client:
            cls.objects.filter(pk=client.pk).update(last_used_at=timezone.now())
        return client
