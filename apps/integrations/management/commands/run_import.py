from django.core.management.base import BaseCommand, CommandError

from apps.integrations.models import ExternalSystem, SyncRun
from apps.integrations.sync import importers, run_import


class Command(BaseCommand):
    help = (
        "Run importers that pull data from external systems. Exits non-zero if any run "
        "fails, so a scheduler (e.g. an Azure Container Apps job) can alert on it."
    )

    def add_arguments(self, parser):
        parser.add_argument("names", nargs="*", help="Importer names, e.g. kyc.dataverse_cases")
        parser.add_argument("--all", action="store_true", help="Run every enabled importer.")
        parser.add_argument("--list", action="store_true", help="List importers and exit.")

    def handle(self, *args, names, **options):
        available = importers()
        if options["list"]:
            for name, cls in sorted(available.items()):
                self.stdout.write(f"{name}  [{cls.system}]  {cls.description}".rstrip())
            return
        if options["all"]:
            enabled = set(
                ExternalSystem.objects.filter(enabled=True).values_list("slug", flat=True)
            )
            names = sorted(n for n, cls in available.items() if cls.system in enabled)
        elif not names:
            raise CommandError("Name the importers to run, or pass --all or --list.")
        unknown = sorted(set(names) - set(available))
        if unknown:
            raise CommandError(f"Unknown importer(s): {', '.join(unknown)}. See --list.")

        ok = True
        for name in names:
            run = run_import(available[name]())
            self.stdout.write(
                f"{name}: {run.get_status_display()} (fetched {run.fetched}, created "
                f"{run.created}, updated {run.updated}, unchanged {run.unchanged}, "
                f"failed {run.failed})"
            )
            for error in run.errors[:5]:
                self.stderr.write(f"  {error.get('record', '')} {error['error']}".rstrip())
            ok = ok and run.status == SyncRun.Status.SUCCEEDED
        if not ok:
            raise CommandError("One or more imports did not fully succeed.")
