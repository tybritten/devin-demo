from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RefundsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.refunds"
    label = "refunds"
    verbose_name = "Refunds"

    def ready(self):
        from .roles import ensure_roles

        post_migrate.connect(ensure_roles, sender=self)
