"""Users are deactivated, never deleted, so their audit trail and record links survive."""

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.db.models.signals import pre_delete


def deactivate(users):
    """Deactivate each user with a normal save so the change is audited. Returns the count."""
    count = 0
    for user in users:
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
            count += 1
    return count


def reactivate(users):
    count = 0
    for user in users:
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
            count += 1
    return count


def _refuse_deletion(sender, instance, **kwargs):
    raise ProtectedError(
        f"Users can't be deleted (audit trail); deactivate {instance.get_username()!r} instead.",
        {instance},
    )


def connect():
    pre_delete.connect(
        _refuse_deletion, sender=get_user_model(), dispatch_uid="core:no-user-delete"
    )
