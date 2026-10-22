from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FlagsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.flags"
    label = "flags"
    verbose_name = "Feature flags"

    def ready(self):
        from .roles import ensure_roles

        post_migrate.connect(ensure_roles, sender=self)
