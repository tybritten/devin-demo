"""Business rules for __Title__. Views call these; nothing else mutates records."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils.text import Truncator

from .models import __Model__, __Model__Event

Status = __Model__.Status
Kind = __Model__Event.Kind

TRANSITIONS = {
    Status.OPEN: {Status.IN_PROGRESS, Status.DONE, Status.CANCELLED},
    Status.IN_PROGRESS: {Status.OPEN, Status.DONE, Status.CANCELLED},
    Status.DONE: set(),
    Status.CANCELLED: set(),
}
COMMENT_REQUIRED = {Status.CANCELLED}
EDITABLE_FIELDS = ["title", "description", "owner"]
ADD_PERM = "__app__.add___model__"
CHANGE_PERM = "__app__.change___model__"


def can_edit(record, user):
    return record.is_open and user.has_perm(CHANGE_PERM)


def allowed_transitions(record, user):
    """Target statuses `user` may move `record` to, in display order."""
    if not user.has_perm(CHANGE_PERM):
        return []
    return [s for s in Status if s in TRANSITIONS[record.status]]


def _log(record, kind, actor, message="", **fields):
    return __Model__Event.objects.create(
        record=record, kind=kind, actor=actor, message=message, **fields
    )


def _show(value):
    return Truncator(str(value)).chars(80) if value not in (None, "") else "—"


@transaction.atomic
def create_record(*, actor, **fields):
    if not actor.has_perm(ADD_PERM):
        raise PermissionDenied
    record = __Model__.objects.create(created_by=actor, **fields)
    _log(record, Kind.CREATED, actor)
    return record


@transaction.atomic
def update_record(record, *, actor, **fields):
    if unknown := set(fields) - set(EDITABLE_FIELDS):
        raise ValueError(f"Not editable: {', '.join(sorted(unknown))}")
    record = __Model__.objects.select_for_update().get(pk=record.pk)
    if not can_edit(record, actor):
        raise PermissionDenied
    changes = []
    for name, new in fields.items():
        old = getattr(record, name)
        if old != new:
            label = record._meta.get_field(name).verbose_name.capitalize()
            changes.append(f"{label}: {_show(old)} → {_show(new)}")
            setattr(record, name, new)
    if changes:
        record.save()
        _log(record, Kind.UPDATED, actor, "\n".join(changes))
    return record


@transaction.atomic
def transition(record, *, to_status, actor, comment=""):
    record = __Model__.objects.select_for_update().get(pk=record.pk)
    if not actor.has_perm(CHANGE_PERM):
        raise PermissionDenied
    if to_status not in TRANSITIONS[record.status]:
        target = dict(Status.choices).get(to_status, to_status)
        raise ValidationError(f"Can't move from {record.get_status_display()} to {target}.")
    comment = comment.strip()
    if to_status in COMMENT_REQUIRED and not comment:
        raise ValidationError("A comment is required for this change.")
    from_status, record.status = record.status, to_status
    record.save(update_fields=["status", "updated_at"])
    _log(
        record,
        Kind.STATUS_CHANGED,
        actor,
        comment,
        from_status=from_status,
        to_status=to_status,
    )
    return record


def add_comment(record, *, actor, message):
    if not actor.has_perm(CHANGE_PERM):
        raise PermissionDenied
    if not message.strip():
        raise ValidationError("Comment can't be empty.")
    return _log(record, Kind.COMMENT, actor, message.strip())
