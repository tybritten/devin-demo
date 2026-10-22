from django.core.management.base import BaseCommand

from apps.audit.roles import AUDITOR_GROUP
from apps.core.demo import check_demo_allowed, demo_user


class Command(BaseCommand):
    help = "Create the demo auditor user. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        demo_user("auditor", "Ari", "Auditor", AUDITOR_GROUP)
        self.stdout.write("Audit demo user: auditor")
