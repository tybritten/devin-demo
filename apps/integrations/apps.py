from apps.core.registry import OpsAppConfig


class IntegrationsConfig(OpsAppConfig):
    name = "apps.integrations"
    label = "integrations"
    verbose_name = "Integrations"
    nav_url_name = "integrations:system_list"
    access_permission = "integrations.view_externalsystem"
    order = 800
