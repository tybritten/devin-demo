from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.audit.log import Action, record
from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "Delete audit entries older than AUDIT_RETENTION_DAYS. Run daily from a scheduled job."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Override retention (days).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, days=None, dry_run=False, **options):
        days = days if days is not None else settings.AUDIT_RETENTION_DAYS
        if days < 1:
            self.stderr.write("Retention must be at least 1 day.")
            return
        cutoff = timezone.now() - timedelta(days=days)
        old = AuditLog.objects.filter(created_at__lt=cutoff)
        if dry_run:
            self.stdout.write(f"Would delete {old.count()} entries older than {cutoff:%Y-%m-%d}.")
            return
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Only this transaction may delete; the trigger blocks every other UPDATE/DELETE.
                cursor.execute("SET LOCAL audit.allow_purge = 'on'")
            deleted, _ = old.delete()
            record(
                Action.PURGE,
                actor=None,
                actor_label="system:purge_audit_log",
                changes={
                    "older_than": cutoff.isoformat(),
                    "deleted": deleted,
                    "retention_days": days,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} audit entries."))
