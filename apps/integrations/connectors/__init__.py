"""Connectors to external systems. Apps get one with `connect("<system slug>")`.

crm = connect("crm-prod")
for row in crm.query("contacts", select=["fullname"], filter="statecode eq 0"):
    ...
crm.update("contacts", contact_id, {"jobtitle": "CFO"})  # ReadOnlySystemError if read-only
"""

from ..errors import IntegrationError
from ..models import ExternalSystem
from .base import Connector
from .dataverse import DataverseConnector
from .sharepoint import SharePointConnector

CONNECTORS = {
    ExternalSystem.Kind.DATAVERSE: DataverseConnector,
    ExternalSystem.Kind.SHAREPOINT: SharePointConnector,
}

__all__ = ["CONNECTORS", "Connector", "DataverseConnector", "SharePointConnector", "connect"]


def connect(system, **kwargs):
    """A connector for an `ExternalSystem` or its slug."""
    if not isinstance(system, ExternalSystem):
        try:
            system = ExternalSystem.objects.get(slug=system)
        except ExternalSystem.DoesNotExist:
            raise IntegrationError(f"No external system with slug {system!r}.") from None
    return CONNECTORS[system.kind](system, **kwargs)
