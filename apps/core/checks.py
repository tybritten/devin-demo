from django.core.checks import Error, register
from django.urls import NoReverseMatch, reverse

from .registry import ops_apps


@register()
def check_ops_apps(app_configs, **kwargs):
    errors = []
    for app in ops_apps():
        if not app.name.startswith("apps."):
            errors.append(Error(f"{app.name}: ops apps must live under apps/.", id="core.E001"))
        if not app.access_permission or "." not in app.access_permission:
            errors.append(
                Error(
                    f"{app.name}: set access_permission to 'app_label.codename'.",
                    id="core.E002",
                )
            )
        if not app.nav_url_name:
            errors.append(Error(f"{app.name}: set nav_url_name.", id="core.E003"))
        else:
            try:
                reverse(app.nav_url_name)
            except NoReverseMatch:
                errors.append(
                    Error(
                        f"{app.name}: nav_url_name {app.nav_url_name!r} does not resolve.",
                        id="core.E004",
                    )
                )
    return errors
