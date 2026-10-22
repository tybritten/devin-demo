from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.demo import check_demo_allowed, demo_user
from apps.integrations.models import ExternalSystem, SyncRun
from apps.integrations.roles import ADMIN_GROUP

DEMO_TENANT = "00000000-0000-0000-0000-000000000000"


class Command(BaseCommand):
    help = "Register two disabled demo systems with sample runs. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        user = demo_user("integrator", "Ira", "Integrator", ADMIN_GROUP)
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        crm, _ = ExternalSystem.objects.update_or_create(
            slug="crm-demo",
            defaults={
                "name": "CRM (Dataverse, demo)",
                "kind": ExternalSystem.Kind.DATAVERSE,
                "access": ExternalSystem.Access.READ_ONLY,
                "base_url": "https://contoso-demo.crm.dynamics.com",
                "tenant_id": DEMO_TENANT,
                "client_id": "11111111-1111-1111-1111-111111111111",
                "client_secret_env": "CRM_DEMO_CLIENT_SECRET",
                "enabled": False,
                "notes": "Demo only: points at a placeholder environment.",
            },
        )
        ExternalSystem.objects.update_or_create(
            slug="ops-sharepoint-demo",
            defaults={
                "name": "Ops SharePoint (demo)",
                "kind": ExternalSystem.Kind.SHAREPOINT,
                "access": ExternalSystem.Access.READ_WRITE,
                "base_url": "https://contoso-demo.sharepoint.com/sites/ops",
                "tenant_id": DEMO_TENANT,
                "client_id": "22222222-2222-2222-2222-222222222222",
                "client_secret_env": "OPS_SHAREPOINT_DEMO_CLIENT_SECRET",
                "enabled": False,
            },
        )
        if not crm.runs.exists():
            now = timezone.now()
            SyncRun.objects.create(
                system=crm,
                job="demo.contacts",
                status=SyncRun.Status.SUCCEEDED,
                started_at=now - timedelta(hours=2),
                finished_at=now - timedelta(hours=2, seconds=-14),
                fetched=120,
                created=4,
                updated=9,
                unchanged=107,
            )
            SyncRun.objects.create(
                system=crm,
                job="demo.contacts",
                status=SyncRun.Status.FAILED,
                started_at=now - timedelta(minutes=30),
                finished_at=now - timedelta(minutes=30),
                errors=[{"error": "CredentialError: crm-demo: Entra rejected the token request"}],
            )
        self.stdout.write(
            "Integrations demo: user integrator, systems crm-demo, ops-sharepoint-demo"
        )
