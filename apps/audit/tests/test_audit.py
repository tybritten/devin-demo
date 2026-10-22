from datetime import timedelta

import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.roles import AUDITOR_GROUP
from apps.core.tests.factories import UserFactory
from apps.flags.models import ApiClient
from apps.flags.tests.factories import FlagFactory
from apps.kyc.models import CaseDocument
from apps.kyc.tests.factories import ReviewCaseFactory

Action = AuditLog.Action
pytestmark = pytest.mark.django_db


def entries(action, obj=None, **filters):
    if obj is not None:
        filters.update(content_type=ContentType.objects.get_for_model(obj), object_id=str(obj.pk))
    return AuditLog.objects.filter(action=action, **filters)


@pytest.fixture
def auditor():
    user = UserFactory(username="auditor")
    user.groups.add(Group.objects.get(name=AUDITOR_GROUP))
    return user


def test_model_create_and_update_are_diffed():
    flag = FlagFactory(key="beta.checkout", enabled=False)
    created = entries(Action.CREATE, flag).get()
    assert created.content_type.model == "featureflag"
    assert created.changes["fields"]["key"] == "beta.checkout"

    flag.enabled = True
    flag.save()
    updated = entries(Action.UPDATE, flag).get()
    assert updated.changes["fields"] == {"enabled": [False, True]}

    flag.save()  # no-op save writes nothing
    assert entries(Action.UPDATE, flag).count() == 1


def test_secrets_are_masked():
    user = UserFactory(username="masked")
    user.set_password("a-new-secret-pw")
    user.save()
    old, new = entries(Action.UPDATE, user).get().changes["fields"]["password"]
    assert old.startswith("********") and new.startswith("********") and old != new
    assert "pbkdf2" not in str(entries(Action.UPDATE, user).values("changes"))

    client = ApiClient(name="svc")
    raw = client.set_new_token()
    client.save()
    logged = entries(Action.CREATE, client).get().changes["fields"]["token_hash"]
    assert logged.startswith("********") and client.token_hash not in logged and raw not in logged


def test_request_context_is_captured(client):
    reviewer = UserFactory(username="kycviewer")
    reviewer.groups.add(Group.objects.get(name="KYC Reviewer"))
    client.force_login(reviewer)
    case = ReviewCaseFactory()
    resp = client.get(case.get_absolute_url(), HTTP_USER_AGENT="pytest", REMOTE_ADDR="10.1.2.3")
    assert resp.status_code == 200
    view = entries(Action.VIEW, case).get()
    assert view.actor == reviewer and view.actor_label == "kycviewer"
    assert view.ip_address == "10.1.2.3" and view.user_agent == "pytest"
    assert view.request_id == resp["X-Request-ID"] and view.path == case.get_absolute_url()


def test_upstream_request_id_and_proxy_ip(client, settings):
    settings.AUDIT_PROXY_COUNT = 1
    client.post(
        reverse("login"),
        {"username": "nobody", "password": "x"},
        HTTP_X_REQUEST_ID="azure-fd-12345678",
        HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
    )
    failed = entries(Action.LOGIN_FAILED).get()
    assert failed.request_id == "azure-fd-12345678"
    assert failed.ip_address == "10.0.0.1"
    client.get(reverse("login"), HTTP_X_REQUEST_ID="bad id with spaces")
    assert not AuditLog.objects.filter(request_id="bad id with spaces").exists()


def test_document_download_is_logged(client):
    reviewer = UserFactory(username="dl")
    reviewer.groups.add(Group.objects.get(name="KYC Reviewer"))
    doc = CaseDocument.objects.create(
        case=ReviewCaseFactory(),
        document_type=CaseDocument.DocumentType.choices[0][0],
        file=SimpleUploadedFile("id.pdf", b"%PDF"),
        original_name="id.pdf",
    )
    client.force_login(reviewer)
    assert client.get(reverse("kyc:document_download", args=[doc.pk])).status_code == 200
    assert entries(Action.DOWNLOAD, doc, actor=reviewer).exists()


def test_login_logout_and_failed_login(client):
    UserFactory(username="alice")
    client.post(reverse("login"), {"username": "alice", "password": "wrong"})
    failed = entries(Action.LOGIN_FAILED).get()
    assert failed.changes == {"username": "alice"} and failed.actor is None
    client.post(reverse("login"), {"username": "alice", "password": "pw"})
    assert entries(Action.LOGIN, actor_label="alice").exists()
    client.post(reverse("logout"))
    assert entries(Action.LOGOUT, actor_label="alice").exists()


def test_permission_changes_are_logged():
    user = UserFactory(username="bob")
    group = Group.objects.create(name="Temp")
    user.groups.add(group)
    added = entries(Action.PERMISSION_CHANGE, user).get()
    assert added.changes == {"relation": "groups", "op": "add", "objects": ["Temp"]}

    group.user_set.remove(user)
    removed = entries(Action.PERMISSION_CHANGE, group).get()
    assert removed.changes == {"relation": "user_set", "op": "remove", "objects": ["bob"]}

    group.permissions.add(Permission.objects.get(codename="view_auditlog"))
    group.permissions.clear()
    cleared = entries(Action.PERMISSION_CHANGE, group).first()
    assert cleared.changes["op"] == "clear" and len(cleared.changes["objects"]) == 1


def test_api_access_is_logged(client):
    api = ApiClient(name="checkout-service")
    raw = api.set_new_token()
    api.save()
    FlagFactory(key="x.flag")
    url = reverse("flags:api_flag_evaluate", args=["x.flag"])
    client.get(url, {"target": "u1"}, HTTP_AUTHORIZATION=f"Bearer {raw}")
    logged = entries(Action.API_ACCESS).get()
    assert logged.actor_label == "api:checkout-service"
    assert logged.changes["args"] == {"key": "x.flag"} and logged.changes["query"] == {
        "target": "u1"
    }
    client.get(url, HTTP_AUTHORIZATION="Bearer wrong")
    assert entries(Action.API_ACCESS).count() == 1


def test_entries_are_append_only_in_the_database():
    entry = AuditLog.objects.create(action=Action.VIEW, actor_label="x")
    with pytest.raises(ValueError):
        entry.save()
    for attempt in (
        lambda: AuditLog.objects.filter(pk=entry.pk).update(actor_label="tampered"),
        lambda: AuditLog.objects.filter(pk=entry.pk).delete(),
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            attempt()
    assert AuditLog.objects.get(pk=entry.pk).actor_label == "x"


def test_deleting_a_user_keeps_their_audit_trail():
    user = UserFactory(username="leaver")
    AuditLog.objects.create(action=Action.LOGIN, actor=user, actor_label="leaver")
    user.delete()
    assert entries(Action.LOGIN, actor_label="leaver").exists()


def test_purge_respects_retention(settings):
    settings.AUDIT_RETENTION_DAYS = 365
    old = AuditLog.objects.create(
        action=Action.VIEW, created_at=timezone.now() - timedelta(days=400)
    )
    recent = AuditLog.objects.create(
        action=Action.VIEW, created_at=timezone.now() - timedelta(days=300)
    )
    call_command("purge_audit_log", "--dry-run")
    assert AuditLog.objects.filter(pk=old.pk).exists()
    call_command("purge_audit_log")
    assert not AuditLog.objects.filter(pk=old.pk).exists()
    assert AuditLog.objects.filter(pk=recent.pk).exists()
    assert entries(Action.PURGE).get().changes["deleted"] == 1


def test_viewer_requires_auditor_role(client, auditor):
    outsider = UserFactory(username="nosy")
    client.force_login(outsider)
    assert client.get(reverse("audit:log")).status_code == 403

    AuditLog.objects.create(action=Action.LOGIN_FAILED, actor_label="mallory")
    client.force_login(auditor)
    resp = client.get(reverse("audit:log"), {"action": "login_failed"})
    assert resp.status_code == 200
    assert [e.actor_label for e in resp.context["entries"]] == ["mallory"]
    assert client.get(reverse("audit:log"), {"q": "mallory"}).context["entries"]


def test_login_lockout_after_repeated_failures(client, settings):
    settings.LOGIN_LOCKOUT_ATTEMPTS = 3
    UserFactory(username="carol")
    for _ in range(3):
        client.post(reverse("login"), {"username": "carol", "password": "wrong"})
    resp = client.post(reverse("login"), {"username": "carol", "password": "pw"})
    assert resp.status_code == 200 and "Too many failed sign-in attempts" in resp.text
    assert "_auth_user_id" not in client.session
    assert entries(Action.LOGIN_FAILED, changes__reason="locked_out").count() == 1

    settings.LOGIN_LOCKOUT_MINUTES = 0
    client.post(reverse("login"), {"username": "carol", "password": "pw"})
    assert client.session["_auth_user_id"]


def test_malformed_forwarded_ip_falls_back_to_remote_addr(client, settings):
    settings.AUDIT_PROXY_COUNT = 1
    client.post(
        reverse("login"),
        {"username": "nobody", "password": "x"},
        HTTP_X_FORWARDED_FOR="not-an-ip",
        REMOTE_ADDR="10.9.8.7",
    )
    assert entries(Action.LOGIN_FAILED).get().ip_address == "10.9.8.7"


def test_failed_login_from_a_logged_in_session_has_no_actor(client):
    client.force_login(UserFactory(username="sessionuser"))
    client.post(reverse("login"), {"username": "victim", "password": "x"})
    failed = entries(Action.LOGIN_FAILED).get()
    assert failed.actor is None and failed.actor_label == ""
    assert failed.changes == {"username": "victim"}


def test_lockout_attempts_do_not_extend_the_lock(client, settings):
    settings.LOGIN_LOCKOUT_ATTEMPTS = 2
    UserFactory(username="dave")
    for _ in range(2):
        client.post(reverse("login"), {"username": "dave", "password": "wrong"})
    old = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES + 1)
    with transaction.atomic():
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL audit.allow_purge = 'on'")
        AuditLog.objects.filter(action=Action.LOGIN_FAILED).delete()
    for _ in range(2):
        AuditLog.objects.create(
            action=Action.LOGIN_FAILED, changes={"username": "dave"}, created_at=old
        )
    for _ in range(5):
        AuditLog.objects.create(
            action=Action.LOGIN_FAILED, changes={"username": "dave", "reason": "locked_out"}
        )
    client.post(reverse("login"), {"username": "dave", "password": "pw"})
    assert client.session["_auth_user_id"]
