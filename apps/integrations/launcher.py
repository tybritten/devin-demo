from datetime import timedelta

from django.utils import timezone

from .models import ExternalSystem, SyncRun


def tile(user):
    since = timezone.now() - timedelta(hours=24)
    return {
        "title": "Integrations",
        "description": "Dataverse and SharePoint connections, and the imports that use them.",
        "url_name": "integrations:system_list",
        "stats": [
            ("Systems", ExternalSystem.objects.filter(enabled=True).count()),
            (
                "Read-write",
                ExternalSystem.objects.filter(enabled=True, access="read_write").count(),
            ),
            (
                "Failed 24h",
                SyncRun.objects.filter(started_at__gte=since)
                .exclude(status__in=[SyncRun.Status.SUCCEEDED, SyncRun.Status.RUNNING])
                .count(),
            ),
        ],
    }
