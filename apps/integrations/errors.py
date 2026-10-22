class IntegrationError(Exception):
    """Base class for every failure talking to an external system."""


class CredentialError(IntegrationError):
    """The Entra client secret is missing or the token request was rejected."""


class SystemDisabledError(IntegrationError):
    pass


class ReadOnlySystemError(IntegrationError):
    """A write was attempted against a system registered as read-only."""


class RemoteError(IntegrationError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status
