from apps.core.registry import OpsAppConfig


class FlagsConfig(OpsAppConfig):
    name = "apps.flags"
    label = "flags"
    verbose_name = "Feature flags"
    nav_label = "Feature Flags"
    nav_url_name = "flags:flag_list"
    access_permission = "flags.view_featureflag"
    order = 30
