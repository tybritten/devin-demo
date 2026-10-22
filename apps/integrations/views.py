from collections import defaultdict

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import DetailView, ListView

from .models import ExternalSystem, SyncRun
from .sync import importers


def _importers_by_system():
    by_system = defaultdict(list)
    for name, cls in sorted(importers().items()):
        by_system[cls.system].append(name)
    return by_system


class SystemListView(PermissionRequiredMixin, ListView):
    permission_required = "integrations.view_externalsystem"
    model = ExternalSystem
    template_name = "integrations/system_list.html"
    context_object_name = "systems"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        latest = SyncRun.objects.order_by("system_id", "-started_at").distinct("system_id")
        last_run = {run.system_id: run for run in latest}
        jobs = _importers_by_system()
        for system in ctx["systems"]:
            system.last_run = last_run.get(system.pk)
            system.importer_names = jobs.get(system.slug, [])
        return ctx


class SystemDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "integrations.view_externalsystem"
    model = ExternalSystem
    template_name = "integrations/system_detail.html"
    context_object_name = "system"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["runs"] = self.object.runs.all()[:50]
        ctx["importer_names"] = _importers_by_system().get(self.object.slug, [])
        return ctx
