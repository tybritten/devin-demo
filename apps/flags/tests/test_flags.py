import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client
from django.urls import reverse

from apps.flags import services
from apps.flags.models import ApiClient, FeatureFlag, FlagChange, rollout_bucket

from .factories import FlagFactory

pytestmark = pytest.mark.django_db


def test_evaluation_rules():
    flag = FeatureFlag(key="x", enabled=False, rollout_percentage=100)
    assert not flag.is_enabled_for("u1")
    flag.enabled = True
    assert flag.is_enabled_for("u1") and flag.is_enabled_for(None)
    flag.rollout_percentage, flag.targets = 0, ["vip"]
    assert flag.is_enabled_for("vip") and not flag.is_enabled_for("u1")
    assert not flag.is_enabled_for(None)
    flag.is_archived = True
    assert not flag.is_enabled_for("vip")


def test_percentage_rollout_is_stable_and_monotonic():
    targets = [f"user-{i}" for i in range(2000)]
    at_30 = {t for t in targets if rollout_bucket("checkout.new", t) < 30}
    at_31 = {t for t in targets if rollout_bucket("checkout.new", t) < 31}
    assert 500 < len(at_30) < 700
    assert at_30 <= at_31
    flag = FeatureFlag(key="checkout.new", enabled=True, rollout_percentage=30)
    assert {t for t in targets if flag.is_enabled_for(t)} == at_30


def test_create_and_update_are_audited(flag_editor):
    flag = services.create_flag(actor=flag_editor, key="a.b", name="AB", comment="new")
    assert flag.changes.get().action == FlagChange.Action.CREATED
    services.update_flag(flag, actor=flag_editor, enabled=True, rollout_percentage=10)
    change = flag.changes.first()
    assert change.action == FlagChange.Action.UPDATED
    assert change.changes == {"enabled": [False, True], "rollout_percentage": [0, 10]}
    services.update_flag(flag, actor=flag_editor, enabled=True)
    assert flag.changes.count() == 2


def test_invalid_key_and_percentage(flag_editor):
    with pytest.raises(ValidationError):
        services.create_flag(actor=flag_editor, key="Bad Key", name="x")
    flag = FlagFactory()
    with pytest.raises(ValidationError):
        services.update_flag(flag, actor=flag_editor, rollout_percentage=101)
    with pytest.raises(ValidationError):
        services.update_flag(flag, actor=flag_editor, key="other")


def test_archive_turns_off_and_blocks_edits(flag_editor):
    flag = FlagFactory(enabled=True)
    flag = services.set_archived(flag, archived=True, actor=flag_editor)
    assert flag.is_archived and not flag.enabled
    with pytest.raises(ValidationError):
        services.update_flag(flag, actor=flag_editor, enabled=True)
    services.set_archived(flag, archived=False, actor=flag_editor)
    assert [c.action for c in flag.changes.all()] == ["restored", "archived"]


def test_audited_flag_cannot_be_deleted(flag_editor):
    flag = services.create_flag(actor=flag_editor, key="a.b", name="AB")
    with pytest.raises(ProtectedError):
        flag.delete()


def test_viewer_is_read_only(client, flag_viewer):
    flag = FlagFactory()
    client.force_login(flag_viewer)
    assert client.get(reverse("flags:flag_list")).status_code == 200
    resp = client.get(flag.get_absolute_url(), {"target": "u1"})
    assert resp.status_code == 200 and resp.context["form"] is None
    assert client.post(flag.get_absolute_url(), {"name": "x"}).status_code == 403
    assert client.post(reverse("flags:flag_toggle", args=[flag.pk])).status_code == 403
    assert client.get(reverse("flags:flag_create")).status_code == 403


def test_outsider_is_forbidden(client, outsider):
    client.force_login(outsider)
    assert client.get(reverse("flags:flag_list")).status_code == 403


def test_editor_creates_edits_and_toggles(client, flag_editor):
    client.force_login(flag_editor)
    resp = client.post(
        reverse("flags:flag_create"),
        {"key": "new.thing", "name": "New", "rollout_percentage": 0, "targets": "a\nb, a"},
    )
    flag = FeatureFlag.objects.get(key="new.thing")
    assert resp.status_code == 302 and flag.targets == ["a", "b"]
    client.post(
        flag.get_absolute_url(),
        {"name": "Renamed", "rollout_percentage": 50, "enabled": "on", "comment": "go"},
    )
    flag.refresh_from_db()
    assert flag.name == "Renamed" and flag.enabled and flag.key == "new.thing"
    client.post(reverse("flags:flag_toggle", args=[flag.pk]))
    flag.refresh_from_db()
    assert not flag.enabled
    assert flag.changes.count() == 3


@pytest.fixture
def token(db):
    client = ApiClient(name="checkout-service")
    raw = client.set_new_token()
    client.save()
    return raw


def test_api_requires_token(client):
    FlagFactory()
    assert client.get(reverse("flags:api_flag_list")).status_code == 401
    resp = client.get(reverse("flags:api_flag_list"), HTTP_AUTHORIZATION="Bearer nope")
    assert resp.status_code == 401


def test_api_list_and_evaluate(client, token):
    FlagFactory(key="on.flag", enabled=True, rollout_percentage=0, targets=["vip"])
    FlagFactory(key="gone.flag", is_archived=True)
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    data = client.get(reverse("flags:api_flag_list"), **auth).json()
    assert [f["key"] for f in data["flags"]] == ["on.flag"]
    url = reverse("flags:api_flag_evaluate", args=["on.flag"])
    assert client.get(url, {"target": "vip"}, **auth).json()["enabled"] is True
    assert client.get(url, {"target": "joe"}, **auth).json()["enabled"] is False
    missing = reverse("flags:api_flag_evaluate", args=["gone.flag"])
    assert client.get(missing, **auth).status_code == 404
    assert Client(enforce_csrf_checks=True).post(url, **auth).status_code == 405
    assert ApiClient.objects.get().last_used_at is not None


def test_inactive_token_rejected(client, token):
    ApiClient.objects.update(is_active=False)
    resp = client.get(reverse("flags:api_flag_list"), HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp.status_code == 401
