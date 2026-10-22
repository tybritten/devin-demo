from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """System-wide, append-only audit trail.

    A Postgres trigger (migration 0001) rejects UPDATE and DELETE; only `purge_audit_log`
    may delete rows past the retention period. Foreign keys have no DB constraint so
    deleting a user or content type never touches audit rows.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VIEW = "view", "View"
        DOWNLOAD = "download", "Download"
        LOGIN = "login", "Login"
        LOGIN_FAILED = "login_failed", "Login failed"
        LOGOUT = "logout", "Logout"
        PERMISSION_CHANGE = "permission_change", "Permission change"
        API_ACCESS = "api_access", "API access"
        PURGE = "purge", "Retention purge"

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_label = models.CharField(max_length=150, blank=True, db_index=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
    )
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.actor_label or 'system'} {self.action}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit entries are append-only.")
        super().save(*args, **kwargs)
