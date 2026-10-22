from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import ListView

from .forms import AuditFilterForm
from .models import AuditLog


class AuditLogView(PermissionRequiredMixin, ListView):
    permission_required = "audit.view_auditlog"
    template_name = "audit/log.html"
    context_object_name = "entries"
    paginate_by = 50

    def get_queryset(self):
        self.filter_form = AuditFilterForm(self.request.GET or None)
        qs = AuditLog.objects.select_related("content_type")
        return self.filter_form.filter(qs) if self.request.GET else qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = self.filter_form
        return ctx
