import re

from ..errors import IntegrationError
from ..models import ExternalSystem
from .base import Connector

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
GUID = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
ODATA = {"OData-MaxVersion": "4.0", "OData-Version": "4.0"}


class DataverseConnector(Connector):
    """Dataverse Web API (the store behind model-driven and most canvas Power Apps).

    `entity_set` is the table's plural set name, e.g. "contacts" or "cr123_kyccases".
    """

    kind = ExternalSystem.Kind.DATAVERSE
    api_path = "/api/data/v9.2"

    @property
    def root(self):
        return self.system.base_url.rstrip("/")

    @property
    def scope(self):
        return f"{self.root}/.default"

    def _url(self, entity_set, record_id=None):
        if not NAME.match(entity_set):
            raise IntegrationError(f"Invalid Dataverse entity set name: {entity_set!r}")
        url = f"{self.root}{self.api_path}/{entity_set}"
        if record_id is not None:
            if not GUID.match(str(record_id)):
                raise IntegrationError(f"Invalid Dataverse record ID: {record_id!r}")
            url += f"({record_id})"
        return url

    def ping(self):
        return self.get_json(f"{self.root}{self.api_path}/WhoAmI", headers=ODATA)

    def query(self, entity_set, *, select=None, filter=None, orderby=None, page_size=1000):
        params = {}
        if select:
            params["$select"] = ",".join(select)
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby
        headers = {**ODATA, "Prefer": f"odata.maxpagesize={page_size}"}
        return self.paged(self._url(entity_set), params=params or None, headers=headers)

    def get(self, entity_set, record_id, *, select=None):
        params = {"$select": ",".join(select)} if select else None
        return self.get_json(self._url(entity_set, record_id), params=params, headers=ODATA)

    def create(self, entity_set, data):
        headers = {**ODATA, "Prefer": "return=representation"}
        resp = self.write(
            "POST", self._url(entity_set), resource=entity_set, json=data, headers=headers
        )
        return resp.json()

    def update(self, entity_set, record_id, data):
        # If-Match: * makes PATCH update-only; without it Dataverse would create a missing row.
        self.write(
            "PATCH",
            self._url(entity_set, record_id),
            resource=entity_set,
            record_id=record_id,
            json=data,
            headers={**ODATA, "If-Match": "*"},
        )
