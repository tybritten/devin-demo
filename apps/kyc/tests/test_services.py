import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.kyc import services
from apps.kyc.models import CaseEvent, ReviewCase

from .factories import CustomerFactory, ReviewCaseFactory

Status = ReviewCase.Status
pytestmark = pytest.mark.django_db


def test_create_case_logs_event(reviewer):
    case = services.create_case(customer=CustomerFactory(), actor=reviewer, risk_rating="low")
    assert case.status == Status.NEW
    assert case.created_by == reviewer
    assert list(case.events.values_list("kind", flat=True)) == [CaseEvent.Kind.CREATED]


def test_start_review_auto_assigns(reviewer):
    case = ReviewCaseFactory()
    case = services.transition(case, to_status=Status.IN_REVIEW, actor=reviewer)
    assert case.status == Status.IN_REVIEW
    assert case.assigned_to == reviewer


def test_invalid_transition_rejected(approver):
    case = ReviewCaseFactory()
    with pytest.raises(ValidationError):
        services.transition(case, to_status=Status.APPROVED, actor=approver)


def test_reviewer_cannot_decide(reviewer):
    case = ReviewCaseFactory(status=Status.IN_REVIEW)
    assert Status.APPROVED not in services.allowed_transitions(case, reviewer)
    with pytest.raises(PermissionDenied):
        services.transition(case, to_status=Status.APPROVED, actor=reviewer)


def test_approver_decision_records_decider(approver):
    case = ReviewCaseFactory(status=Status.IN_REVIEW)
    case = services.transition(case, to_status=Status.APPROVED, actor=approver)
    assert case.decided_by == approver
    assert case.decided_at is not None
    event = case.events.get(kind=CaseEvent.Kind.STATUS_CHANGED)
    assert (event.from_status, event.to_status) == (Status.IN_REVIEW, Status.APPROVED)


def test_high_risk_approval_needs_extra_permission(approver):
    from django.contrib.auth.models import Permission

    approver.groups.first().permissions.remove(Permission.objects.get(codename="approve_high_risk"))
    approver = type(approver).objects.get(pk=approver.pk)
    case = ReviewCaseFactory(status=Status.IN_REVIEW, risk_rating=ReviewCase.Risk.HIGH)
    allowed = services.allowed_transitions(case, approver)
    assert Status.APPROVED not in allowed
    assert Status.REJECTED in allowed


@pytest.mark.parametrize("to_status", [Status.PENDING_INFO, Status.ESCALATED, Status.REJECTED])
def test_comment_required(approver, to_status):
    case = ReviewCaseFactory(status=Status.IN_REVIEW)
    with pytest.raises(ValidationError):
        services.transition(case, to_status=to_status, actor=approver, comment="  ")
    services.transition(case, to_status=to_status, actor=approver, comment="Need utility bill")


def test_closed_case_cannot_be_reassigned(reviewer):
    case = ReviewCaseFactory(status=Status.APPROVED)
    with pytest.raises(ValidationError):
        services.assign(case, assignee=reviewer, actor=reviewer)


def test_assign_logs_event(reviewer, approver):
    case = ReviewCaseFactory()
    services.assign(case, assignee=reviewer, actor=approver)
    services.assign(case, assignee=reviewer, actor=approver)
    assert case.events.filter(kind=CaseEvent.Kind.ASSIGNED).count() == 1
