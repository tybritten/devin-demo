import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.kyc import services
from apps.kyc.models import Customer, ReviewCase
from apps.kyc.roles import APPROVER_GROUP, REVIEWER_GROUP

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "0.0.0.0"}
DEMO_USERS = [
    ("reviewer", "Riley", "Reviewer", REVIEWER_GROUP),
    ("approver", "Avery", "Approver", APPROVER_GROUP),
]
NAMES = [
    "Ada Lovelace",
    "Grace Hopper",
    "Alan Turing",
    "Katherine Johnson",
    "Linus Pauling",
    "Acme Holdings Ltd",
    "Globex Corporation",
    "Initech LLC",
    "Umbrella Trading",
    "Stark Imports",
]


class Command(BaseCommand):
    help = "Create demo users (password: demo) and sample KYC cases. DEBUG only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed demo data with DEBUG=False.")
        if not set(settings.ALLOWED_HOSTS) <= LOCAL_HOSTS:
            raise CommandError("Refusing to seed demo users when ALLOWED_HOSTS is not local-only.")
        User = get_user_model()
        users = []
        for username, first, last, group in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "last_name": last}
            )
            if created:
                user.set_password("demo")
                user.save()
            user.groups.add(Group.objects.get(name=group))
            users.append(user)

        rng = random.Random(42)
        today = timezone.localdate()
        for i, name in enumerate(NAMES):
            customer, _ = Customer.objects.get_or_create(
                external_ref=f"CRM-{1000 + i}",
                defaults={
                    "legal_name": name,
                    "customer_type": "business" if i >= 5 else "individual",
                    "country": rng.choice(["US", "GB", "CA", "DE", "SG"]),
                },
            )
            if customer.cases.exists():
                continue
            case = services.create_case(
                customer=customer,
                actor=users[1],
                review_type=rng.choice(ReviewCase.ReviewType.values),
                risk_rating=rng.choice(ReviewCase.Risk.values),
                due_date=today + timedelta(days=rng.randint(-3, 14)),
                summary="Seeded demo case.",
            )
            if i % 3 == 1:
                services.transition(case, to_status="in_review", actor=users[0])
        self.stdout.write(
            self.style.SUCCESS("Seeded demo data. Log in as reviewer/demo or approver/demo.")
        )
