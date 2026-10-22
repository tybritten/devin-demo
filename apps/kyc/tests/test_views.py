import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.kyc.models import CaseDocument, Customer, ReviewCase

from .factories import CustomerFactory, ReviewCaseFactory

Status = ReviewCase.Status
pytestmark = pytest.mark.django_db


def test_login_required(client):
    resp = client.get(reverse("kyc:queue"))
    assert resp.status_code == 302
    assert reverse("login") in resp["Location"]


def test_healthz_is_public(client):
    assert client.get(reverse("healthz")).json() == {"status": "ok"}


def test_outsider_forbidden(client, outsider):
    client.force_login(outsider)
    assert client.get(reverse("kyc:queue")).status_code == 403


def test_queue_scopes_and_search(client, reviewer):
    mine = ReviewCaseFactory(assigned_to=reviewer, customer=CustomerFactory(legal_name="Mine Co"))
    unassigned = ReviewCaseFactory(customer=CustomerFactory(legal_name="Free Co"))
    closed = ReviewCaseFactory(status=Status.APPROVED)
    client.force_login(reviewer)

    resp = client.get(reverse("kyc:queue"))
    assert list(resp.context["cases"]) == [mine]

    resp = client.get(reverse("kyc:queue"), {"scope": "unassigned"})
    assert list(resp.context["cases"]) == [unassigned]

    resp = client.get(reverse("kyc:queue"), {"scope": "closed"})
    assert list(resp.context["cases"]) == [closed]

    resp = client.get(reverse("kyc:queue"), {"scope": "open", "q": "free"})
    assert list(resp.context["cases"]) == [unassigned]

    resp = client.get(reverse("kyc:queue"), {"scope": "open", "q": mine.reference})
    assert list(resp.context["cases"]) == [mine]


def test_create_case_reuses_customer_by_external_ref(client, reviewer):
    existing = CustomerFactory(external_ref="CRM-1", legal_name="Old Name")
    client.force_login(reviewer)
    resp = client.post(
        reverse("kyc:case_create"),
        {
            "customer_type": "individual",
            "legal_name": "New Name",
            "external_ref": "CRM-1",
            "country": "gb",
            "review_type": "periodic",
            "risk_rating": "low",
        },
    )
    case = ReviewCase.objects.get()
    assert resp.status_code == 302 and resp["Location"] == case.get_absolute_url()
    assert Customer.objects.count() == 1
    existing.refresh_from_db()
    assert (existing.legal_name, existing.country) == ("Old Name", "US")
    assert case.customer == existing and case.created_by == reviewer


def test_detail_and_workflow(client, reviewer, approver):
    case = ReviewCaseFactory()
    client.force_login(reviewer)
    assert client.get(case.get_absolute_url()).status_code == 200

    client.post(reverse("kyc:case_claim", args=[case.pk]))
    client.post(reverse("kyc:case_transition", args=[case.pk]), {"to_status": "in_review"})
    client.post(reverse("kyc:case_comment", args=[case.pk]), {"message": "Looks fine"})
    resp = client.post(reverse("kyc:case_transition", args=[case.pk]), {"to_status": "approved"})
    case.refresh_from_db()
    assert case.status == Status.IN_REVIEW and case.assigned_to == reviewer
    assert "not allowed" in str(list(resp.wsgi_request._messages)[-1])

    client.force_login(approver)
    client.post(reverse("kyc:case_transition", args=[case.pk]), {"to_status": "approved"})
    case.refresh_from_db()
    assert case.status == Status.APPROVED and case.decided_by == approver
    assert case.events.count() == 4  # assigned, status, comment, status


def test_document_upload_and_download(client, reviewer, outsider):
    case = ReviewCaseFactory()
    client.force_login(reviewer)
    upload = SimpleUploadedFile("passport.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    client.post(
        reverse("kyc:document_upload", args=[case.pk]),
        {"document_type": "passport", "file": upload},
    )
    doc = CaseDocument.objects.get()
    assert doc.original_name == "passport.pdf"

    resp = client.get(reverse("kyc:document_download", args=[doc.pk]))
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == b"%PDF-1.4 test"

    client.force_login(outsider)
    assert client.get(reverse("kyc:document_download", args=[doc.pk])).status_code == 403


def test_document_upload_rejects_bad_extension(client, reviewer):
    case = ReviewCaseFactory()
    client.force_login(reviewer)
    upload = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
    client.post(
        reverse("kyc:document_upload", args=[case.pk]),
        {"document_type": "other", "file": upload},
    )
    assert not CaseDocument.objects.exists()


def test_document_upload_blocked_on_closed_case(client, reviewer):
    case = ReviewCaseFactory(status=Status.APPROVED)
    client.force_login(reviewer)
    upload = SimpleUploadedFile("late.pdf", b"%PDF", content_type="application/pdf")
    client.post(
        reverse("kyc:document_upload", args=[case.pk]),
        {"document_type": "other", "file": upload},
    )
    assert not CaseDocument.objects.exists()


def test_media_not_publicly_routed(client, reviewer, settings):
    client.force_login(reviewer)
    assert client.get("/media/kyc/anything.pdf").status_code == 404
