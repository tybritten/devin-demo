"""The current request, so audit entries written from signals know who did what, from where."""

from contextlib import contextmanager
from contextvars import ContextVar

_current_request = ContextVar("audit_request", default=None)
_system_actor = ContextVar("audit_system_actor", default="")


def current_request():
    return _current_request.get()


def system_actor():
    return _system_actor.get()


@contextmanager
def acting_as(label):
    """Attribute entries written outside a request (imports, scheduled jobs) to `label`."""
    token = _system_actor.set(label)
    try:
        yield
    finally:
        _system_actor.reset(token)
