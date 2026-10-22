from decimal import Decimal

import pytest
from django.urls import reverse

from apps.refunds import services
from apps.refunds.models import Refund

from .factories import RefundFactory

pytestmark = pytest.mark.django_db


def test_outsider_is_forbidden(client, outsider):
    client.force_login(outsider)
    assert client.get(reverse("refunds:dashboard")).status_code == 403
    assert client.get(reverse("refunds:refund_list")).status_code == 403


def test_dashboard_and_list_render(client, refund_approver):
    RefundFactory(amount=Decimal("42.00"))
    client.force_login(refund_approver)
    resp = client.get(reverse("refunds:dashboard"))
    assert resp.status_code == 200
    assert len(resp.context["approvals"]) == 1
    assert (
        client.get(reverse("refunds:refund_list"), {"scope": "all", "q": "RF-"}).status_code == 200
    )


def test_home_shows_refund_tile(client, refund_approver):
    client.force_login(refund_approver)
    assert b"Pending approval" in client.get("/").content


def test_create_refund(client, refund_requester):
    client.force_login(refund_requester)
    resp = client.post(
        reverse("refunds:refund_create"),
        {"customer_name": "Ada", "amount": "25.00", "reason": "billing_error"},
    )
    refund = Refund.objects.get()
    assert resp.status_code == 302 and resp.url == refund.get_absolute_url()
    assert refund.requested_by == refund_requester


def test_approver_cannot_create(client, refund_approver):
    client.force_login(refund_approver)
    assert client.get(reverse("refunds:refund_create")).status_code == 403


def test_transition_view_enforces_service_rules(client, refund_approver):
    refund = services.create_refund(
        actor=refund_approver, customer_name="Ada", amount=Decimal("10"), reason="other"
    )
    client.force_login(refund_approver)
    client.post(reverse("refunds:refund_transition", args=[refund.pk]), {"to_status": "approved"})
    refund.refresh_from_db()
    assert refund.status == Refund.Status.REQUESTED


def test_transition_and_comment_views(client, refund_approver):
    refund = RefundFactory()
    client.force_login(refund_approver)
    client.post(reverse("refunds:refund_transition", args=[refund.pk]), {"to_status": "approved"})
    client.post(reverse("refunds:refund_comment", args=[refund.pk]), {"message": "ok"})
    refund.refresh_from_db()
    assert refund.status == Refund.Status.APPROVED
    resp = client.get(refund.get_absolute_url())
    assert resp.status_code == 200 and b"ok" in resp.content
