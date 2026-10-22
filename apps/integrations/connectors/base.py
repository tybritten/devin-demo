from urllib.parse import urlsplit

import requests
from django.core.exceptions import ValidationError

from apps.audit.log import Action, record

from ..credentials import get_token
from ..errors import IntegrationError, ReadOnlySystemError, RemoteError, SystemDisabledError
from ..http import build_session


class Connector:
    """Authenticated client for one `ExternalSystem`. Subclasses add the system's API.

    Every write goes through `write()`, which refuses read-only systems and audits the call.
    """

    kind = None

    def __init__(self, system, *, session=None):
        if system.kind != self.kind:
            raise IntegrationError(f"{system.slug} is a {system.kind} system, not {self.kind}.")
        if not system.enabled:
            raise SystemDisabledError(f"{system.slug} is disabled.")
        try:
            system.clean()
        except ValidationError as exc:
            raise IntegrationError(f"{system.slug} is misconfigured: {exc.messages}") from exc
        self.system = system
        self.session = session or build_session()
        self.timeout = system.timeout_seconds

    @property
    def scope(self):
        raise NotImplementedError

    def ping(self):
        """Cheapest authenticated call that proves the credentials and URL work."""
        raise NotImplementedError

    @property
    def allowed_hosts(self):
        """Hosts this connector may send its bearer token to."""
        raise NotImplementedError

    def request(self, method, url, *, headers=None, **kwargs):
        parts = urlsplit(url)
        if parts.scheme != "https" or (parts.hostname or "").lower() not in self.allowed_hosts:
            raise IntegrationError(f"{self.system.slug}: refusing to send credentials to {url!r}.")
        token = get_token(self.system, self.scope, self.session)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            **(headers or {}),
        }
        where = f"{self.system.slug}: {method} {urlsplit(url).path}"
        try:
            resp = self.session.request(
                method, url, headers=headers, timeout=self.timeout, allow_redirects=False, **kwargs
            )
        except requests.Timeout as exc:
            raise RemoteError(f"{where} timed out after {self.timeout}s") from exc
        except requests.RequestException as exc:
            raise RemoteError(f"{where} failed ({exc.__class__.__name__})") from exc
        if resp.status_code >= 300:
            raise RemoteError(
                f"{where} returned {resp.status_code}: {_remote_message(resp)}",
                status=resp.status_code,
            )
        return resp

    def get_json(self, url, **kwargs):
        try:
            return self.request("GET", url, **kwargs).json()
        except ValueError as exc:
            raise RemoteError(
                f"{self.system.slug}: GET {urlsplit(url).path} returned invalid JSON"
            ) from exc

    def paged(self, url, *, params=None, headers=None):
        """Yield every item of an OData collection, following `@odata.nextLink`."""
        host = urlsplit(url).hostname
        while url:
            data = self.get_json(url, params=params, headers=headers)
            yield from data.get("value", [])
            url, params = data.get("@odata.nextLink"), None
            if url and urlsplit(url).hostname != host:
                raise RemoteError(f"{self.system.slug}: next page points at another host.")

    def write(self, method, url, *, resource, record_id="", json=None, headers=None, fields=None):
        details = {
            "system": self.system.slug,
            "method": method,
            "resource": resource,
            "record_id": str(record_id),
            # Field names only: values may be customer data.
            "fields": sorted(fields if fields is not None else (json or {})),
        }
        if not self.system.is_writable:
            record(Action.EXTERNAL_WRITE, obj=self.system, changes={**details, "blocked": True})
            raise ReadOnlySystemError(
                f"{self.system.slug} is read-only; refused {method} {resource}."
            )
        if callable(url):  # resolved only once the write is allowed (it may need a lookup)
            url = url()
        resp = self.request(method, url, json=json, headers=headers)
        record(Action.EXTERNAL_WRITE, obj=self.system, changes=details)
        return resp


def _remote_message(resp):
    """The error message from an OData/Graph error body, without echoing request data."""
    try:
        error = resp.json().get("error", {})
    except ValueError:
        return resp.reason or ""
    if isinstance(error, dict):
        return " ".join(filter(None, [error.get("code"), error.get("message")]))[:300]
    return str(error)[:300]
