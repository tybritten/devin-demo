"""The current request, so audit entries written from signals know who did what, from where."""

from contextvars import ContextVar

_current_request = ContextVar("audit_request", default=None)


def current_request():
    return _current_request.get()
