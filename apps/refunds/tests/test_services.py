from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import ProtectedError

from apps.refunds import services
from apps.refunds.models import Refund, RefundEvent

from .factories import RefundFactory

pytestmark = pytest.mark.django_db
S = Refund.Status


def make(requester, amount="100.00"):
    return services.create_refund(
        actor=requester, customer_name="Ada", amount=Decimal(amount), reason="billing_error"
    )


def test_create_records_event(refund_requester):
    refund = make(refund_requester)
    assert refund.status == S.REQUESTED
    assert refund.requested_by == refund_requester
    assert refund.events.get().kind == RefundEvent.Kind.CREATED


def test_create_rejects_non_positive_amount(refund_requester):
    with pytest.raises(ValidationError):
        make(refund_requester, "0")


def test_full_happy_path(refund_requester, refund_approver, refund_finance):
    refund = make(refund_requester)
    refund = services.transition(refund, to_status=S.APPROVED, actor=refund_approver)
    assert refund.decided_by == refund_approver and refund.decided_at
    with pytest.raises(ValidationError, match="payment reference"):
        services.transition(refund, to_status=S.PAID, actor=refund_finance)
    refund = services.transition(
        refund, to_status=S.PAID, actor=refund_finance, payment_reference=" PAY-1 "
    )
    assert refund.paid_by == refund_finance and refund.payment_reference == "PAY-1"
    assert refund.events.count() == 3


def test_requester_cannot_approve_own_refund(refund_approver):
    refund = make(refund_approver)
    assert S.APPROVED not in services.allowed_transitions(refund, refund_approver)
    with pytest.raises(PermissionDenied):
        services.transition(refund, to_status=S.APPROVED, actor=refund_approver)


def test_over_limit_needs_senior_approver(
    settings, refund_requester, refund_approver, refund_senior
):
    settings.REFUND_APPROVAL_LIMIT = Decimal("500")
    refund = make(refund_requester, "500.01")
    assert refund.over_limit
    assert services.allowed_transitions(refund, refund_approver) == [S.REJECTED, S.CANCELLED]
    with pytest.raises(PermissionDenied):
        services.transition(refund, to_status=S.APPROVED, actor=refund_approver)
    services.transition(refund, to_status=S.APPROVED, actor=refund_senior)


def test_at_limit_is_regular_approval(settings, refund_requester, refund_approver):
    settings.REFUND_APPROVAL_LIMIT = Decimal("500")
    refund = make(refund_requester, "500.00")
    services.transition(refund, to_status=S.APPROVED, actor=refund_approver)


def test_reject_and_cancel_require_comment(refund_requester, refund_approver):
    refund = make(refund_requester)
    with pytest.raises(ValidationError):
        services.transition(refund, to_status=S.REJECTED, actor=refund_approver, comment=" ")
    with pytest.raises(ValidationError):
        services.transition(refund, to_status=S.CANCELLED, actor=refund_requester)
    services.transition(refund, to_status=S.CANCELLED, actor=refund_requester, comment="dupe")


def test_requester_cannot_cancel_others_or_approved(refund_requester, refund_approver):
    other = RefundFactory()
    assert services.allowed_transitions(other, refund_requester) == []
    mine = make(refund_requester)
    services.transition(mine, to_status=S.APPROVED, actor=refund_approver)
    mine.refresh_from_db()
    assert services.allowed_transitions(mine, refund_requester) == []


def test_only_finance_marks_paid(refund_requester, refund_approver, refund_finance):
    refund = services.transition(
        make(refund_requester), to_status=S.APPROVED, actor=refund_approver
    )
    assert S.PAID not in services.allowed_transitions(refund, refund_approver)
    assert S.PAID in services.allowed_transitions(refund, refund_finance)


def test_closed_refunds_cannot_move(refund_requester, refund_approver):
    refund = services.transition(
        make(refund_requester), to_status=S.REJECTED, actor=refund_approver, comment="no"
    )
    with pytest.raises(ValidationError):
        services.transition(refund, to_status=S.APPROVED, actor=refund_approver)


def test_audited_refund_cannot_be_deleted(refund_requester):
    with pytest.raises(ProtectedError):
        make(refund_requester).delete()
