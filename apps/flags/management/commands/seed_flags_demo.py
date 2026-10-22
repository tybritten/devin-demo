from django.core.management.base import BaseCommand

from apps.core.demo import check_demo_allowed, demo_user
from apps.flags import services
from apps.flags.models import FeatureFlag
from apps.flags.roles import EDITOR_GROUP, VIEWER_GROUP

FLAGS = [
    ("checkout.new_flow", "New checkout flow", True, 25, ["customer-1001", "customer-1002"]),
    ("billing.invoice_pdf_v2", "Invoice PDF v2", True, 100, []),
    ("search.semantic", "Semantic search", False, 0, []),
    ("support.chat_widget", "In-app support chat", True, 0, ["user-qa-1"]),
]


class Command(BaseCommand):
    help = "Create demo flag users and sample flags. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        engineer = demo_user("engineer", "Emery", "Engineer", EDITOR_GROUP)
        demo_user("approver", "Avery", "Approver", VIEWER_GROUP)
        for key, name, enabled, pct, targets in FLAGS:
            if not FeatureFlag.objects.filter(key=key).exists():
                services.create_flag(
                    actor=engineer,
                    key=key,
                    name=name,
                    enabled=enabled,
                    rollout_percentage=pct,
                    targets=targets,
                    owner=engineer,
                    comment="Seeded demo flag.",
                )
        self.stdout.write(self.style.SUCCESS("Seeded feature-flag demo data."))
