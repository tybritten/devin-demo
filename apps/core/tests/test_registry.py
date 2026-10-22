import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.core.registry import ops_apps

pytestmark = pytest.mark.django_db


def test_ops_apps_are_discovered():
    assert [a.label for a in ops_apps()] == ["kyc", "refunds", "flags"]


def test_ops_app_roles_are_synced():
    for app in ops_apps():
        for group_name, codenames in app.roles().items():
            granted = set(
                Group.objects.get(name=group_name).permissions.values_list("codename", flat=True)
            )
            assert set(codenames) <= granted, group_name


def test_nav_only_lists_accessible_apps(client, refund_approver):
    client.force_login(refund_approver)
    nav = client.get(reverse("home")).context["ops_nav"]
    assert [a.label for a in nav] == ["refunds"]
