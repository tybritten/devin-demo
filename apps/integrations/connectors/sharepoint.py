import re
from urllib.parse import quote, urlsplit

from ..errors import IntegrationError
from ..models import ExternalSystem
from .base import Connector

ITEM_ID = re.compile(r"^\d{1,12}$")


class SharePointConnector(Connector):
    """SharePoint lists through Microsoft Graph. `list_name` is the list's name or GUID."""

    kind = ExternalSystem.Kind.SHAREPOINT
    graph = "https://graph.microsoft.com/v1.0"
    scope = "https://graph.microsoft.com/.default"

    def __init__(self, system, **kwargs):
        super().__init__(system, **kwargs)
        self._site_id = None

    @property
    def site_id(self):
        if self._site_id is None:
            parts = urlsplit(self.system.base_url)
            path = parts.path.rstrip("/")
            site = f"{parts.hostname}:{quote(path)}" if path else parts.hostname
            self._site_id = self.get_json(f"{self.graph}/sites/{site}")["id"]
        return self._site_id

    def _list_url(self, list_name, *rest):
        segments = [quote(str(s), safe="") for s in (list_name, *rest)]
        return f"{self.graph}/sites/{self.site_id}/lists/" + "/".join(segments)

    def _item_id(self, item_id):
        if not ITEM_ID.match(str(item_id)):
            raise IntegrationError(f"Invalid SharePoint item ID: {item_id!r}")
        return str(item_id)

    @property
    def allowed_hosts(self):
        return {urlsplit(self.graph).hostname}

    def ping(self):
        return {"site_id": self.site_id}

    def items(self, list_name, *, fields=None, filter=None, page_size=200):
        """Yield list items as `{"id": ..., **fields}`."""
        expand = f"fields(select={','.join(fields)})" if fields else "fields"
        params = {"expand": expand, "$top": page_size}
        headers = {}
        if filter:
            params["$filter"] = filter
            headers["Prefer"] = "HonorNonIndexedQueriesWarningMayFailRandomly"
        for item in self.paged(self._list_url(list_name, "items"), params=params, headers=headers):
            yield {"id": item["id"], **item.get("fields", {})}

    def create_item(self, list_name, fields):
        resp = self.write(
            "POST",
            lambda: self._list_url(list_name, "items"),
            resource=f"list:{list_name}",
            json={"fields": fields},
            fields=fields,
        )
        return resp.json()

    def update_item(self, list_name, item_id, fields):
        item_id = self._item_id(item_id)
        self.write(
            "PATCH",
            lambda: self._list_url(list_name, "items", item_id, "fields"),
            resource=f"list:{list_name}",
            record_id=item_id,
            json=fields,
        )
