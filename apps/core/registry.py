"""Ops-app registry.

Every workflow app subclasses `OpsAppConfig`. Core discovers those configs to mount URLs,
build the navbar, collect home-page tiles and sync default roles, so adding an app never
means editing core or `config/`.
"""

from importlib import import_module

from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate
from django.urls import include, path
from django.utils.module_loading import import_string


class OpsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Django only auto-selects an AppConfig if it's the sole `default` one in apps.py, and
    # importing this base class there would otherwise make two.
    default = False

    # URL prefix the app is mounted under; defaults to "<label>/".
    url_prefix = None
    # Navbar link text; defaults to `verbose_name`.
    nav_label = None
    # Named URL the navbar link and home tile point to, e.g. "kyc:queue".
    nav_url_name = None
    # Permission ("app_label.codename") that gates the navbar link and home tile.
    access_permission = None
    # Lower sorts first in the navbar and on the home page.
    order = 100

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.default = cls.__dict__.get("default", True)

    def ready(self):
        self.url_prefix = self.url_prefix or f"{self.label}/"
        self.nav_label = self.nav_label or str(self.verbose_name)
        post_migrate.connect(self._sync_roles, sender=self)

    def _sync_roles(self, **kwargs):
        from .roles import sync_roles

        sync_roles(self.label, self.roles())

    def _optional_module(self, name):
        try:
            return import_module(f"{self.name}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{self.name}.{name}":
                raise
            return None

    def roles(self):
        """{group name: [permission codenames]} from the app's `roles.ROLES`."""
        module = self._optional_module("roles")
        return getattr(module, "ROLES", {}) if module else {}

    def user_has_access(self, user):
        return user.is_authenticated and user.has_perm(self.access_permission)

    def tile(self, user):
        """The app's home-page tile from `launcher.tile(user)`, or None."""
        if not self.user_has_access(user) or not self._optional_module("launcher"):
            return None
        return import_string(f"{self.name}.launcher.tile")(user)


def ops_apps():
    configs = [c for c in apps.get_app_configs() if isinstance(c, OpsAppConfig)]
    return sorted(configs, key=lambda c: (c.order, c.nav_label))


def ops_urlpatterns():
    return [path(c.url_prefix, include(f"{c.name}.urls")) for c in ops_apps()]
