"""Scheduled pulls from external systems into an app.

An app adds `importers.py` with `Importer` subclasses listed in `IMPORTERS`;
`manage.py run_import <name>` (or `--all`) runs them and records a `SyncRun` per run.
"""

from enum import StrEnum

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from apps.audit.context import acting_as
from apps.core.registry import ops_apps

from .connectors import connect
from .errors import IntegrationError
from .models import ExternalSystem, SyncRun

MAX_ERRORS = 50


class Result(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class Importer:
    name = None  # "<app label>.<what>", e.g. "kyc.dataverse_cases"
    system = None  # ExternalSystem slug
    description = ""

    def fetch(self, connector):
        """Yield source records (dicts) from `connector`."""
        raise NotImplementedError

    def apply(self, record):
        """Create or update local data through the app's services; return a `Result`.

        Runs in its own transaction: an exception rolls back this record only.
        """
        raise NotImplementedError

    def describe(self, record):
        """Short identifier for a record in error reports."""
        return str(record.get("id", ""))


def importers():
    found = {}
    for app in ops_apps():
        module = app._optional_module("importers")
        for cls in getattr(module, "IMPORTERS", []):
            if not cls.name or not cls.system:
                raise ImproperlyConfigured(f"{cls.__qualname__} needs `name` and `system`.")
            if cls.name in found:
                raise ImproperlyConfigured(f"Duplicate importer name {cls.name!r}.")
            found[cls.name] = cls
    return found


def run_import(importer, *, connector=None):
    system = ExternalSystem.objects.get(slug=importer.system)
    run = SyncRun.objects.create(system=system, job=importer.name)
    try:
        with acting_as(f"import:{importer.name}"):
            connector = connector or connect(system)
            for record in importer.fetch(connector):
                run.fetched += 1
                try:
                    with transaction.atomic():
                        result = Result(importer.apply(record))
                except Exception as exc:  # noqa: BLE001 - one bad record must not stop the run
                    run.failed += 1
                    _add_error(run, exc, importer.describe(record))
                else:
                    setattr(run, result.value, getattr(run, result.value) + 1)
    except IntegrationError as exc:
        run.status = SyncRun.Status.FAILED
        _add_error(run, exc)
    except Exception as exc:
        run.status = SyncRun.Status.FAILED
        _add_error(run, exc)
        _finish(run)
        raise
    else:
        run.status = SyncRun.Status.PARTIAL if run.failed else SyncRun.Status.SUCCEEDED
    _finish(run)
    return run


def _add_error(run, exc, record=""):
    if len(run.errors) < MAX_ERRORS:
        entry = {"error": f"{exc.__class__.__name__}: {exc}"[:500]}
        if record:
            entry["record"] = record[:100]
        run.errors.append(entry)


def _finish(run):
    run.finished_at = timezone.now()
    run.save()
