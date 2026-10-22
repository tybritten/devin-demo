from django.core.management.base import BaseCommand

from apps.__app__ import services
from apps.__app__.models import __Model__
from apps.__app__.roles import EDITOR_GROUP
from apps.core.demo import check_demo_allowed, demo_user


class Command(BaseCommand):
    help = "Seed demo data for __Title__. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        editor = demo_user("__app___editor", "Demo", "Editor", EDITOR_GROUP)
        if not __Model__.objects.exists():
            for title in ["First example", "Second example"]:
                services.create_record(actor=editor, title=title, owner=editor)
        self.stdout.write(self.style.SUCCESS("Seeded __Title__ demo data."))
