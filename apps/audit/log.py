"""Write audit entries. `record()` fills in actor and request details from the current request."""

import ipaddress

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.text import Truncator

from .context import current_request
from .models import AuditLog

Action = AuditLog.Action
FROM_REQUEST = object()


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def client_ip(request):
    """REMOTE_ADDR, or the client address added by our own proxies (AUDIT_PROXY_COUNT hops)."""
    hops = settings.AUDIT_PROXY_COUNT
    forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p]
    if hops and len(forwarded) >= hops and (ip := _valid_ip(forwarded[-hops])):
        return ip
    return _valid_ip(request.META.get("REMOTE_ADDR", ""))


def record(action, *, obj=None, changes=None, actor=FROM_REQUEST, actor_label="", request=None):
    """Write one entry. `actor` defaults to the request's user; pass `actor=None` for none."""
    request = request or current_request()
    if actor is FROM_REQUEST:
        user = getattr(request, "user", None)
        actor = user if user is not None and user.is_authenticated else None
    entry = AuditLog(
        action=action,
        actor=actor,
        actor_label=actor_label or (actor.get_username() if actor else ""),
        changes=changes or {},
    )
    if obj is not None:
        entry.content_type = ContentType.objects.get_for_model(obj)
        entry.object_id = str(obj.pk)
        entry.object_repr = Truncator(str(obj)).chars(255)
    if request is not None:
        entry.ip_address = client_ip(request)
        entry.user_agent = request.headers.get("User-Agent", "")[:255]
        entry.request_id = getattr(request, "request_id", "")
        entry.method = request.method or ""
        entry.path = request.path[:255]
    entry.save()
    return entry


def log_view(request, obj, action=Action.VIEW):
    """Record that the current user looked at (or downloaded) a sensitive record."""
    return record(action, obj=obj, request=request)
