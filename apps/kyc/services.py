"""Business rules for KYC cases. Views call these; they never mutate case state directly."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CaseDocument, CaseEvent, ReviewCase

Status = ReviewCase.Status

TRANSITIONS = {
    Status.NEW: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.PENDING_INFO, Status.ESCALATED, Status.APPROVED, Status.REJECTED},
    Status.PENDING_INFO: {Status.IN_REVIEW},
    Status.ESCALATED: {Status.IN_REVIEW, Status.APPROVED, Status.REJECTED},
    Status.APPROVED: set(),
    Status.REJECTED: set(),
}
DECISION_STATUSES = {Status.APPROVED, Status.REJECTED}
COMMENT_REQUIRED = {Status.PENDING_INFO, Status.ESCALATED, Status.REJECTED}


def allowed_transitions(case, user):
    """Target statuses `user` may move `case` to, in display order."""
    targets = TRANSITIONS[case.status]
    if not user.has_perm("kyc.decide_case"):
        targets = targets - DECISION_STATUSES
    if case.risk_rating == ReviewCase.Risk.HIGH and not user.has_perm("kyc.approve_high_risk"):
        targets = targets - {Status.APPROVED}
    return [s for s in Status if s in targets]


@transaction.atomic
def create_case(*, customer, actor, **fields):
    case = ReviewCase.objects.create(customer=customer, created_by=actor, **fields)
    CaseEvent.objects.create(
        case=case, kind=CaseEvent.Kind.CREATED, actor=actor, to_status=case.status
    )
    return case


@transaction.atomic
def assign(case, *, assignee, actor):
    case = ReviewCase.objects.select_for_update().get(pk=case.pk)
    if not case.is_open:
        raise ValidationError("Closed cases cannot be reassigned.")
    if case.assigned_to_id == (assignee.pk if assignee else None):
        return case
    case.assigned_to = assignee
    case.save(update_fields=["assigned_to", "updated_at"])
    CaseEvent.objects.create(
        case=case,
        kind=CaseEvent.Kind.ASSIGNED,
        actor=actor,
        message=f"Assigned to {assignee.get_full_name() or assignee.username}"
        if assignee
        else "Unassigned",
    )
    return case


@transaction.atomic
def transition(case, *, to_status, actor, comment=""):
    case = ReviewCase.objects.select_for_update().get(pk=case.pk)
    to_status = Status(to_status)
    comment = comment.strip()

    if to_status not in TRANSITIONS[case.status]:
        raise ValidationError(
            f"Cannot move a case from {case.get_status_display()} to {to_status.label}."
        )
    if to_status not in allowed_transitions(case, actor):
        raise PermissionDenied(f"You are not allowed to move this case to {to_status.label}.")
    if to_status in COMMENT_REQUIRED and not comment:
        raise ValidationError(f"A comment is required to move a case to {to_status.label}.")

    from_status = case.status
    case.status = to_status
    update_fields = ["status", "updated_at"]
    if to_status == Status.IN_REVIEW and case.assigned_to_id is None:
        case.assigned_to = actor
        update_fields.append("assigned_to")
    if to_status in DECISION_STATUSES:
        case.decided_by = actor
        case.decided_at = timezone.now()
        update_fields += ["decided_by", "decided_at"]
    case.save(update_fields=update_fields)

    CaseEvent.objects.create(
        case=case,
        kind=CaseEvent.Kind.STATUS_CHANGED,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        message=comment,
    )
    return case


def add_comment(case, *, actor, message):
    message = message.strip()
    if not message:
        raise ValidationError("Comment cannot be empty.")
    return CaseEvent.objects.create(
        case=case, kind=CaseEvent.Kind.COMMENT, actor=actor, message=message
    )


@transaction.atomic
def add_document(case, *, actor, document_type, file):
    doc = CaseDocument.objects.create(
        case=case,
        document_type=document_type,
        file=file,
        original_name=file.name,
        uploaded_by=actor,
    )
    CaseEvent.objects.create(
        case=case, kind=CaseEvent.Kind.DOCUMENT_ADDED, actor=actor, message=str(doc)
    )
    return doc
