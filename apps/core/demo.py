"""Helpers for the local-only `seed_*_demo` commands."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import CommandError

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "0.0.0.0"}
DEMO_PASSWORD = "demo"


def check_demo_allowed():
    if not settings.DEBUG:
        raise CommandError("Refusing to seed demo data with DEBUG=False.")
    if not set(settings.ALLOWED_HOSTS) <= LOCAL_HOSTS:
        raise CommandError("Refusing to seed demo users when ALLOWED_HOSTS is not local-only.")


def demo_user(username, first_name, last_name, *groups):
    user, created = get_user_model().objects.get_or_create(
        username=username, defaults={"first_name": first_name, "last_name": last_name}
    )
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save()
    user.groups.add(*Group.objects.filter(name__in=groups))
    return user
