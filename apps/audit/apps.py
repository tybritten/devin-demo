from apps.core.registry import OpsAppConfig


class AuditConfig(OpsAppConfig):
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit log"
    nav_url_name = "audit:log"
    access_permission = "audit.view_auditlog"
    order = 900

    def ready(self):
        super().ready()
        from . import signals

        signals.connect()
