"""Business rules for refunds. Views call these; they never mutate refund state directly."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Refund, RefundEvent

Status = Refund.Status

TRANSITIONS = {
    Status.REQUESTED: {Status.APPROVED, Status.REJECTED, Status.CANCELLED},
    Status.APPROVED: {Status.PAID, Status.CANCELLED},
    Status.PAID: set(),
    Status.REJECTED: set(),
    Status.CANCELLED: set(),
}
DECISIONS = {Status.APPROVED, Status.REJECTED}
COMMENT_REQUIRED = {Status.REJECTED, Status.CANCELLED}


def allowed_transitions(refund, user):
    """Target statuses `user` may move `refund` to, in display order."""
    targets = set(TRANSITIONS[refund.status])
    # Four-eyes: nobody decides a refund they requested.
    if not user.has_perm("refunds.approve_refund") or refund.requested_by_id == user.pk:
        targets -= DECISIONS
    if refund.over_limit and not user.has_perm("refunds.approve_over_limit"):
        targets.discard(Status.APPROVED)
    if not user.has_perm("refunds.mark_paid"):
        targets.discard(Status.PAID)
    own_request = refund.status == Status.REQUESTED and refund.requested_by_id == user.pk
    if not (
        own_request or user.has_perm("refunds.approve_refund") or user.has_perm("refunds.mark_paid")
    ):
        targets.discard(Status.CANCELLED)
    return [s for s in Status if s in targets]


@transaction.atomic
def create_refund(*, actor, **fields):
    refund = Refund(requested_by=actor, **fields)
    refund.full_clean()
    refund.save()
    RefundEvent.objects.create(
        refund=refund, kind=RefundEvent.Kind.CREATED, actor=actor, to_status=refund.status
    )
    return refund


@transaction.atomic
def transition(refund, *, to_status, actor, comment="", payment_reference=""):
    refund = Refund.objects.select_for_update().get(pk=refund.pk)
    to_status = Status(to_status)
    comment = comment.strip()
    payment_reference = payment_reference.strip()

    if to_status not in TRANSITIONS[refund.status]:
        raise ValidationError(
            f"Cannot move a refund from {refund.get_status_display()} to {to_status.label}."
        )
    if to_status not in allowed_transitions(refund, actor):
        raise PermissionDenied(f"You are not allowed to move this refund to {to_status.label}.")
    if to_status in COMMENT_REQUIRED and not comment:
        raise ValidationError(f"A comment is required to move a refund to {to_status.label}.")
    if to_status == Status.PAID and not payment_reference:
        raise ValidationError("A payment reference is required to mark a refund as paid.")

    from_status = refund.status
    refund.status = to_status
    update_fields = ["status", "updated_at"]
    if to_status in DECISIONS:
        refund.decided_by = actor
        refund.decided_at = timezone.now()
        update_fields += ["decided_by", "decided_at"]
    if to_status == Status.PAID:
        refund.paid_by = actor
        refund.paid_at = timezone.now()
        refund.payment_reference = payment_reference
        update_fields += ["paid_by", "paid_at", "payment_reference"]
    refund.save(update_fields=update_fields)

    message = comment
    if payment_reference:
        message = f"Payment reference: {payment_reference}" + (f"\n{comment}" if comment else "")
    RefundEvent.objects.create(
        refund=refund,
        kind=RefundEvent.Kind.STATUS_CHANGED,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        message=message,
    )
    return refund


def add_comment(refund, *, actor, message):
    message = message.strip()
    if not message:
        raise ValidationError("Comment cannot be empty.")
    return RefundEvent.objects.create(
        refund=refund, kind=RefundEvent.Kind.COMMENT, actor=actor, message=message
    )
