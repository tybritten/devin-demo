from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.core.demo import check_demo_allowed

SEED_COMMANDS = ["seed_kyc_demo", "seed_refunds_demo", "seed_flags_demo"]


class Command(BaseCommand):
    help = "Seed demo users and data for every app. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        for name in SEED_COMMANDS:
            call_command(name, stdout=self.stdout)
        self.stdout.write(
            self.style.SUCCESS(
                "Demo users: reviewer, approver, finance, engineer (password: demo)."
            )
        )
