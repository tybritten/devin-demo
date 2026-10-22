import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import ProtectedError

from apps.__app__ import services
from apps.__app__.models import __Model__

pytestmark = pytest.mark.django_db
Status = __Model__.Status


def test_create_writes_event(editor):
    record = services.create_record(actor=editor, title="First")
    assert record.created_by == editor
    assert list(record.events.values_list("kind", flat=True)) == ["created"]


def test_viewer_cannot_create(viewer):
    with pytest.raises(PermissionDenied):
        services.create_record(actor=viewer, title="Nope")


def test_update_records_field_diff(editor):
    record = services.create_record(actor=editor, title="Old")
    services.update_record(record, actor=editor, title="New")
    record.refresh_from_db()
    assert record.title == "New"
    assert "Old → New" in record.events.first().message


def test_update_rejects_unknown_fields(editor):
    record = services.create_record(actor=editor, title="Locked")
    with pytest.raises(ValueError):
        services.update_record(record, actor=editor, status=Status.DONE)


def test_transition_is_audited_and_terminal(editor):
    record = services.create_record(actor=editor, title="Flow")
    services.transition(record, to_status=Status.DONE, actor=editor)
    record.refresh_from_db()
    event = record.events.first()
    assert record.status == Status.DONE
    assert (event.from_status, event.to_status) == (Status.OPEN, Status.DONE)
    with pytest.raises(ValidationError):
        services.transition(record, to_status=Status.OPEN, actor=editor)
    with pytest.raises(PermissionDenied):
        services.update_record(record, actor=editor, title="Too late")


def test_cancel_requires_comment(editor):
    record = services.create_record(actor=editor, title="Cancel me")
    with pytest.raises(ValidationError):
        services.transition(record, to_status=Status.CANCELLED, actor=editor)
    services.transition(record, to_status=Status.CANCELLED, actor=editor, comment="Duplicate")


def test_viewer_cannot_change(editor, viewer):
    record = services.create_record(actor=editor, title="Hands off")
    with pytest.raises(PermissionDenied):
        services.transition(record, to_status=Status.DONE, actor=viewer)
    with pytest.raises(PermissionDenied):
        services.update_record(record, actor=viewer, title="Nope")
    with pytest.raises(PermissionDenied):
        services.add_comment(record, actor=viewer, message="Nope")


def test_audited_records_cannot_be_deleted(editor):
    record = services.create_record(actor=editor, title="Keep")
    with pytest.raises(ProtectedError):
        record.delete()
