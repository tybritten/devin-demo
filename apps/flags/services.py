"""Business rules for feature flags. Every change writes a `FlagChange`."""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import FeatureFlag, FlagChange

EDITABLE_FIELDS = ["name", "description", "enabled", "rollout_percentage", "targets", "owner"]


def _snapshot(flag):
    data = {f: getattr(flag, f) for f in EDITABLE_FIELDS if f != "owner"}
    data["targets"] = list(flag.targets)
    data["owner"] = flag.owner.username if flag.owner else None
    return data


def _diff(before, after):
    return {k: [before.get(k), after[k]] for k in after if before.get(k) != after[k]}


@transaction.atomic
def create_flag(*, actor, key, comment="", **fields):
    flag = FeatureFlag(key=key, **fields)
    flag.full_clean()
    flag.save()
    FlagChange.objects.create(
        flag=flag,
        action=FlagChange.Action.CREATED,
        actor=actor,
        changes=_diff({}, _snapshot(flag)),
        comment=comment.strip(),
    )
    return flag


@transaction.atomic
def update_flag(flag, *, actor, comment="", **fields):
    unknown = set(fields) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(f"Cannot change {', '.join(sorted(unknown))}.")
    flag = FeatureFlag.objects.select_for_update().get(pk=flag.pk)
    if flag.is_archived:
        raise ValidationError("Archived flags can't be changed. Restore it first.")
    before = _snapshot(flag)
    for name, value in fields.items():
        setattr(flag, name, value)
    flag.full_clean()
    changes = _diff(before, _snapshot(flag))
    if not changes:
        return flag
    flag.save()
    FlagChange.objects.create(
        flag=flag,
        action=FlagChange.Action.UPDATED,
        actor=actor,
        changes=changes,
        comment=comment.strip(),
    )
    return flag


@transaction.atomic
def set_archived(flag, *, archived, actor, comment=""):
    flag = FeatureFlag.objects.select_for_update().get(pk=flag.pk)
    if flag.is_archived == archived:
        return flag
    before = _snapshot(flag) | {"is_archived": flag.is_archived}
    flag.is_archived = archived
    if archived:
        flag.enabled = False
    flag.save()
    FlagChange.objects.create(
        flag=flag,
        action=FlagChange.Action.ARCHIVED if archived else FlagChange.Action.RESTORED,
        actor=actor,
        changes=_diff(before, _snapshot(flag) | {"is_archived": flag.is_archived}),
        comment=comment.strip(),
    )
    return flag


def flag_payload(flag):
    """Config a client needs to evaluate the flag locally."""
    return {
        "key": flag.key,
        "enabled": flag.enabled,
        "rollout_percentage": flag.rollout_percentage,
        "targets": list(flag.targets),
        "updated_at": flag.updated_at.isoformat(),
    }
