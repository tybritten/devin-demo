from django.core.management.base import BaseCommand, CommandError

from apps.integrations.connectors import connect
from apps.integrations.errors import IntegrationError


class Command(BaseCommand):
    help = "Authenticate to an external system and make one read call."

    def add_arguments(self, parser):
        parser.add_argument("slug")

    def handle(self, *args, slug, **options):
        try:
            connector = connect(slug)
            connector.ping()
        except IntegrationError as exc:
            raise CommandError(str(exc)) from exc
        system = connector.system
        self.stdout.write(
            self.style.SUCCESS(
                f"{system.name}: connected ({system.get_kind_display()}, "
                f"{system.get_access_display().lower()})"
            )
        )
