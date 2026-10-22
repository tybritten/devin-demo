import random
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.core.demo import check_demo_allowed, demo_user
from apps.refunds import services
from apps.refunds.models import Refund
from apps.refunds.roles import APPROVER_GROUP, FINANCE_GROUP, REQUESTER_GROUP, SENIOR_APPROVER_GROUP

CUSTOMERS = [
    "Ada Lovelace",
    "Grace Hopper",
    "Acme Holdings Ltd",
    "Globex Corporation",
    "Initech LLC",
    "Katherine Johnson",
    "Stark Imports",
    "Umbrella Trading",
]


class Command(BaseCommand):
    help = "Create demo refund users and sample refunds. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        requester = demo_user("reviewer", "Riley", "Reviewer", REQUESTER_GROUP)
        approver = demo_user("approver", "Avery", "Approver", APPROVER_GROUP)
        finance = demo_user("finance", "Frankie", "Finance", SENIOR_APPROVER_GROUP, FINANCE_GROUP)
        if Refund.objects.exists():
            self.stdout.write("Refunds already seeded.")
            return
        rng = random.Random(7)
        for i in range(14):
            refund = services.create_refund(
                actor=requester,
                customer_name=rng.choice(CUSTOMERS),
                customer_ref=f"CRM-{1000 + rng.randint(0, 9)}",
                order_ref=f"ORD-{50000 + i}",
                amount=Decimal(rng.choice([19, 49, 120, 250, 480, 900, 1500, 3200]))
                + Decimal("0.99"),
                reason=rng.choice(Refund.Reason.values),
                description="Seeded demo refund.",
            )
            step = i % 5
            if step >= 1:
                decider = finance if refund.over_limit else approver
                if step == 4:
                    services.transition(
                        refund,
                        to_status="rejected",
                        actor=decider,
                        comment="Outside refund policy.",
                    )
                    continue
                services.transition(refund, to_status="approved", actor=decider)
            if step >= 2:
                services.transition(
                    refund, to_status="paid", actor=finance, payment_reference=f"PAY-{9000 + i}"
                )
        self.stdout.write(self.style.SUCCESS("Seeded refunds demo data."))
