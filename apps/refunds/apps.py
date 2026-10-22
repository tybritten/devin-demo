from apps.core.registry import OpsAppConfig


class RefundsConfig(OpsAppConfig):
    name = "apps.refunds"
    label = "refunds"
    verbose_name = "Refunds"
    nav_url_name = "refunds:dashboard"
    access_permission = "refunds.view_refund"
    order = 20
