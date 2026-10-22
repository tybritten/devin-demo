from django.apps import AppConfig
from django.db.models.signals import post_migrate


class KycConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.kyc"
    label = "kyc"
    verbose_name = "KYC Review"

    def ready(self):
        from .roles import ensure_roles

        post_migrate.connect(ensure_roles, sender=self)
