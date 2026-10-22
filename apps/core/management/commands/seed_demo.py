from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand

from apps.core.demo import check_demo_allowed
from apps.core.registry import ops_apps


class Command(BaseCommand):
    help = "Run every ops app's `seed_<label>_demo` command. Local development only."

    def handle(self, *args, **options):
        check_demo_allowed()
        available = get_commands()
        for app in ops_apps():
            name = f"seed_{app.label}_demo"
            if name in available:
                call_command(name, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Demo users all use the password: demo."))
