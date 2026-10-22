from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import AuditLog


def tile(user):
    since = timezone.now() - timedelta(hours=24)
    counts = AuditLog.objects.filter(created_at__gte=since).aggregate(
        total=Count("pk"),
        failed=Count("pk", filter=Q(action=AuditLog.Action.LOGIN_FAILED)),
        perms=Count("pk", filter=Q(action=AuditLog.Action.PERMISSION_CHANGE)),
    )
    return {
        "title": "Audit log",
        "description": "Who changed, viewed or accessed what, across every app.",
        "url_name": "audit:log",
        "stats": [
            ("Events 24h", counts["total"]),
            ("Failed logins", counts["failed"]),
            ("Perm changes", counts["perms"]),
        ],
    }
