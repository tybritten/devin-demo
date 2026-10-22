import pytest
import requests
import responses
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse
from responses import matchers

from apps.audit.models import AuditLog
from apps.core.tests.factories import UserFactory
from apps.integrations import credentials
from apps.integrations.connectors import connect
from apps.integrations.errors import (
    CredentialError,
    IntegrationError,
    ReadOnlySystemError,
    RemoteError,
    SystemDisabledError,
)
from apps.integrations.models import ExternalSystem, SyncRun
from apps.integrations.roles import VIEWER_GROUP
from apps.integrations.sync import Importer, Result, run_import

TENANT = "aaaaaaaa-0000-0000-0000-000000000001"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
CRM = "https://contoso.crm.dynamics.com"
API = f"{CRM}/api/data/v9.2"
GRAPH = "https://graph.microsoft.com/v1.0"
SECRET = "s3cr3t-client-value"
GUID = "6f9619ff-8b86-d011-b42d-00c04fc964ff"


@pytest.fixture(autouse=True)
def _env(monkeypatch, settings):
    monkeypatch.setenv("CRM_CLIENT_SECRET", SECRET)
    settings.INTEGRATIONS_HTTP_BACKOFF = 0
    credentials.clear_cache()
    yield
    credentials.clear_cache()


@pytest.fixture
def mock():
    with responses.RequestsMock() as rsps:
        yield rsps


def _system(**overrides):
    fields = {
        "slug": "crm",
        "name": "CRM",
        "kind": ExternalSystem.Kind.DATAVERSE,
        "base_url": CRM,
        "tenant_id": TENANT,
        "client_id": "bbbbbbbb-0000-0000-0000-000000000002",
        "client_secret_env": "CRM_CLIENT_SECRET",
        **overrides,
    }
    return ExternalSystem.objects.create(**fields)


@pytest.fixture
def crm(db):
    return _system()


@pytest.fixture
def sharepoint(db):
    return _system(
        slug="ops-sp",
        name="Ops SharePoint",
        kind=ExternalSystem.Kind.SHAREPOINT,
        base_url="https://contoso.sharepoint.com/sites/ops",
        access=ExternalSystem.Access.READ_WRITE,
    )


def _token(mock, scope=f"{CRM}/.default"):
    return mock.post(
        TOKEN_URL,
        json={"access_token": "tok", "expires_in": 3600},
        match=[
            matchers.urlencoded_params_matcher(
                {
                    "grant_type": "client_credentials",
                    "client_id": "bbbbbbbb-0000-0000-0000-000000000002",
                    "client_secret": SECRET,
                    "scope": scope,
                }
            )
        ],
    )


@pytest.mark.parametrize(
    ("kind", "url"),
    [
        ("dataverse", "http://contoso.crm.dynamics.com"),
        ("dataverse", "https://evil.example.com"),
        ("dataverse", "https://contoso.crm.dynamics.com/main.aspx"),
        ("sharepoint", "https://contoso.crm.dynamics.com/sites/ops"),
        ("dataverse", "https://contoso.crm.dynamics.com/?x=1"),
        ("sharepoint", "https://contoso.sharepoint.com:8443/sites/ops"),
    ],
)
def test_urls_are_restricted_to_microsoft_hosts(kind, url):
    with pytest.raises(ValidationError):
        ExternalSystem(kind=kind, base_url=url).clean()


def test_connector_refuses_misconfigured_or_disabled_systems(db):
    with pytest.raises(IntegrationError, match="misconfigured"):
        connect(_system(slug="bad", base_url="https://evil.example.com"))
    with pytest.raises(SystemDisabledError):
        connect(_system(slug="off", enabled=False))
    with pytest.raises(IntegrationError, match="No external system"):
        connect("missing")


def test_dataverse_query_follows_pages_with_one_cached_token(crm, mock):
    token = _token(mock)
    mock.get(
        f"{API}/contacts",
        match=[
            matchers.query_param_matcher({"$select": "fullname", "$filter": "statecode eq 0"}),
            matchers.header_matcher(
                {"Authorization": "Bearer tok", "Prefer": "odata.maxpagesize=2"}
            ),
        ],
        json={"value": [{"id": 1}, {"id": 2}], "@odata.nextLink": f"{API}/contacts?page=2"},
    )
    mock.get(f"{API}/contacts?page=2", json={"value": [{"id": 3}]})
    rows = list(
        connect("crm").query("contacts", select=["fullname"], filter="statecode eq 0", page_size=2)
    )
    assert [r["id"] for r in rows] == [1, 2, 3]
    mock.get(f"{API}/contacts({GUID})", json={"id": 9})
    assert connect("crm").get("contacts", GUID) == {"id": 9}
    assert token.call_count == 1


def test_next_link_to_another_host_is_refused(crm, mock):
    _token(mock)
    mock.get(f"{API}/contacts", json={"value": [], "@odata.nextLink": "https://evil.example.com/x"})
    with pytest.raises(RemoteError, match="another host"):
        list(connect("crm").query("contacts"))


def test_missing_secret_and_rejected_token(crm, mock, monkeypatch):
    mock.post(
        TOKEN_URL,
        status=401,
        json={
            "error": "invalid_client",
            "error_description": "AADSTS7000215: Invalid secret.\nTrace",
        },
    )
    with pytest.raises(CredentialError, match="AADSTS7000215") as exc:
        connect("crm").ping()
    assert SECRET not in str(exc.value)
    monkeypatch.delenv("CRM_CLIENT_SECRET")
    with pytest.raises(CredentialError, match="CRM_CLIENT_SECRET is not set"):
        connect("crm").ping()


def test_reads_retry_on_throttling_but_writes_do_not(sharepoint, mock):
    _token(mock, scope="https://graph.microsoft.com/.default")
    site = f"{GRAPH}/sites/contoso.sharepoint.com:/sites/ops"
    mock.get(site, status=429)
    mock.get(site, json={"id": "site-1"})
    sp = connect("ops-sp")
    assert sp.ping() == {"site_id": "site-1"}
    create = mock.post(f"{GRAPH}/sites/site-1/lists/Vendors/items", status=503)
    with pytest.raises(RemoteError, match="503"):
        sp.create_item("Vendors", {"Title": "Acme"})
    assert create.call_count == 1


def test_timeouts_become_remote_errors(crm, mock):
    _token(mock)
    mock.get(f"{API}/WhoAmI", body=requests.Timeout())
    with pytest.raises(RemoteError, match="timed out after 30s"):
        connect("crm").ping()


def test_names_and_ids_are_validated_before_any_request(crm, mock):
    dv = connect("crm")
    with pytest.raises(IntegrationError, match="entity set"):
        list(dv.query("contacts?$top=1"))
    with pytest.raises(IntegrationError, match="record ID"):
        dv.get("contacts", "1 or 1=1")


def test_read_only_system_refuses_writes_without_calling_out(crm, mock):
    with pytest.raises(ReadOnlySystemError):
        connect("crm").update("contacts", GUID, {"jobtitle": "CFO"})
    assert not mock.calls
    entry = AuditLog.objects.get(action=AuditLog.Action.EXTERNAL_WRITE)
    assert entry.changes["blocked"] is True and entry.object_id == str(crm.pk)


def test_read_write_writes_are_audited_by_field_name(crm, mock):
    crm.access = ExternalSystem.Access.READ_WRITE
    crm.save()
    _token(mock)
    mock.patch(
        f"{API}/contacts({GUID})",
        status=204,
        match=[
            matchers.header_matcher({"If-Match": "*"}),
            matchers.json_params_matcher({"jobtitle": "CFO"}),
        ],
    )
    connect("crm").update("contacts", GUID, {"jobtitle": "CFO"})
    entry = AuditLog.objects.get(action=AuditLog.Action.EXTERNAL_WRITE)
    assert entry.changes == {
        "system": "crm",
        "method": "PATCH",
        "resource": "contacts",
        "record_id": GUID,
        "fields": ["jobtitle"],
    }
    assert "CFO" not in str(entry.changes)


def test_sharepoint_items_and_writes(sharepoint, mock):
    _token(mock, scope="https://graph.microsoft.com/.default")
    mock.get(f"{GRAPH}/sites/contoso.sharepoint.com:/sites/ops", json={"id": "site-1"})
    mock.get(
        f"{GRAPH}/sites/site-1/lists/Vendor%20List/items",
        match=[matchers.query_param_matcher({"expand": "fields(select=Title)", "$top": "200"})],
        json={"value": [{"id": "7", "fields": {"Title": "Acme"}}]},
    )
    mock.patch(f"{GRAPH}/sites/site-1/lists/Vendor%20List/items/7/fields", json={})
    sp = connect("ops-sp")
    assert list(sp.items("Vendor List", fields=["Title"])) == [{"id": "7", "Title": "Acme"}]
    sp.update_item("Vendor List", 7, {"Title": "Acme Ltd"})
    with pytest.raises(IntegrationError):
        sp.update_item("Vendor List", "../7", {})


def test_access_mode_changes_are_audited(crm):
    crm.access = ExternalSystem.Access.READ_WRITE
    crm.save()
    entry = AuditLog.objects.filter(action=AuditLog.Action.UPDATE, object_id=str(crm.pk)).get(
        content_type__model="externalsystem"
    )
    assert entry.changes["fields"]["access"] == ["read_only", "read_write"]


class GroupImporter(Importer):
    name = "test.groups"
    system = "crm"

    def fetch(self, connector):
        yield from connector.query("teams")

    def apply(self, record):
        if record["name"] == "bad":
            raise ValueError("no name")
        _, created = Group.objects.get_or_create(name=record["name"])
        return Result.CREATED if created else Result.UNCHANGED


def test_run_import_counts_results_and_isolates_bad_records(crm, mock):
    Group.objects.create(name="existing")
    _token(mock)
    mock.get(
        f"{API}/teams", json={"value": [{"name": "new"}, {"name": "existing"}, {"name": "bad"}]}
    )
    run = run_import(GroupImporter())
    assert (run.status, run.fetched, run.created, run.unchanged, run.failed) == (
        SyncRun.Status.PARTIAL,
        3,
        1,
        1,
        1,
    )
    assert run.errors == [{"error": "ValueError: no name"}]
    created = AuditLog.objects.get(action=AuditLog.Action.CREATE, object_repr="new")
    assert created.actor_label == "import:test.groups"
    assert not AuditLog.objects.filter(content_type__model="syncrun").exists()


def test_run_import_records_connection_failures(crm, mock):
    _token(mock)
    mock.get(
        f"{API}/teams",
        status=403,
        json={"error": {"code": "0x80040220", "message": "No privilege"}},
    )
    run = run_import(GroupImporter())
    assert run.status == SyncRun.Status.FAILED and run.finished_at
    assert "403: 0x80040220 No privilege" in run.errors[0]["error"]


def test_run_import_command(crm, mock, monkeypatch, capsys):
    monkeypatch.setattr(
        "apps.integrations.management.commands.run_import.importers",
        lambda: {GroupImporter.name: GroupImporter},
    )
    call_command("run_import", "--list")
    assert "test.groups  [crm]" in capsys.readouterr().out
    with pytest.raises(CommandError, match="Unknown importer"):
        call_command("run_import", "nope")
    _token(mock)
    mock.get(f"{API}/teams", json={"value": [{"name": "a"}]})
    call_command("run_import", "--all")
    assert "Succeeded (fetched 1, created 1" in capsys.readouterr().out
    mock.get(f"{API}/teams", status=500)
    with pytest.raises(CommandError, match="did not fully succeed"):
        call_command("run_import", "test.groups")


def test_viewer_sees_systems_but_never_the_secret(client, crm):
    user = UserFactory(username="iviewer")
    user.groups.add(Group.objects.get(name=VIEWER_GROUP))
    client.force_login(user)
    SyncRun.objects.create(system=crm, job="test.groups", status=SyncRun.Status.FAILED)
    listing = client.get(reverse("integrations:system_list"))
    assert listing.status_code == 200 and b"CRM" in listing.content and b"Failed" in listing.content
    detail = client.get(crm.get_absolute_url())
    assert detail.status_code == 200
    assert b"CRM_CLIENT_SECRET" in detail.content and SECRET.encode() not in detail.content


def test_bearer_tokens_only_go_to_the_system_over_https(crm, mock):
    _token(mock)
    mock.get(
        f"{API}/contacts",
        json={
            "value": [],
            "@odata.nextLink": "http://contoso.crm.dynamics.com/api/data/v9.2/contacts?p=2",
        },
    )
    with pytest.raises(IntegrationError, match="refusing to send credentials"):
        list(connect("crm").query("contacts"))
    with pytest.raises(IntegrationError, match="refusing to send credentials"):
        connect("crm").get_json("https://evil.example.com/steal")


def test_redirects_are_not_followed(crm, mock):
    mock.post(TOKEN_URL, status=307, headers={"Location": "https://evil.example.com/token"})
    with pytest.raises(CredentialError, match="307"):
        connect("crm").ping()
    credentials.clear_cache()
    _token(mock)
    mock.get(f"{API}/WhoAmI", status=302, headers={"Location": "https://evil.example.com/x"})
    with pytest.raises(RemoteError, match="302"):
        connect("crm").ping()


def test_malformed_responses_are_remote_errors(crm, mock):
    mock.post(TOKEN_URL, body="<html>")
    with pytest.raises(CredentialError, match="malformed token response"):
        connect("crm").ping()
    credentials.clear_cache()
    _token(mock)
    mock.get(f"{API}/teams", body="<html>")
    run = run_import(GroupImporter())
    assert run.status == SyncRun.Status.FAILED and "invalid JSON" in run.errors[0]["error"]


def test_read_only_sharepoint_refuses_writes_before_any_lookup(sharepoint, mock, monkeypatch):
    sharepoint.access = ExternalSystem.Access.READ_ONLY
    sharepoint.save()
    monkeypatch.delenv("CRM_CLIENT_SECRET")
    sp = connect("ops-sp")
    with pytest.raises(ReadOnlySystemError):
        sp.create_item("Vendors", {"Title": "Acme"})
    with pytest.raises(ReadOnlySystemError):
        sp.update_item("Vendors", 7, {"Title": "Acme"})
    assert not mock.calls
    assert AuditLog.objects.filter(action=AuditLog.Action.EXTERNAL_WRITE).count() == 2
