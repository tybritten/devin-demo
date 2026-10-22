import pytest
from django.urls import reverse

from apps.__app__.models import __Model__

from .factories import __Model__Factory

pytestmark = pytest.mark.django_db


@pytest.fixture
def record(db):
    return __Model__Factory()


def _get_urls(record):
    return [
        reverse("__app__:list"),
        reverse("__app__:create"),
        reverse("__app__:detail", args=[record.pk]),
        reverse("__app__:edit", args=[record.pk]),
    ]


def _post_urls(record):
    return [
        reverse("__app__:transition", args=[record.pk]),
        reverse("__app__:comment", args=[record.pk]),
    ]


def test_anonymous_is_sent_to_login(client, record):
    for url in _get_urls(record) + _post_urls(record):
        resp = client.post(url) if url in _post_urls(record) else client.get(url)
        assert resp.status_code == 302 and "/accounts/login/" in resp.url, url


def test_outsider_is_forbidden_everywhere(client, outsider, record):
    client.force_login(outsider)
    for url in _get_urls(record):
        assert client.get(url).status_code == 403, url
    for url in _post_urls(record):
        assert client.post(url, {"to_status": "done", "message": "x"}).status_code == 403, url
    assert b"__Title__" not in client.get("/").content


def test_viewer_is_read_only(client, viewer, record):
    client.force_login(viewer)
    assert client.get(reverse("__app__:list")).status_code == 200
    assert client.get(record.get_absolute_url()).status_code == 200
    assert client.get(reverse("__app__:create")).status_code == 403
    assert client.get(reverse("__app__:edit", args=[record.pk])).status_code == 403
    resp = client.post(reverse("__app__:transition", args=[record.pk]), {"to_status": "done"})
    assert resp.status_code == 403
    record.refresh_from_db()
    assert record.status == __Model__.Status.OPEN


def test_editor_end_to_end(client, editor):
    client.force_login(editor)
    assert b"__Title__" in client.get("/").content
    resp = client.post(reverse("__app__:create"), {"title": "From the UI"})
    record = __Model__.objects.get()
    assert resp.status_code == 302 and resp.url == record.get_absolute_url()
    client.post(reverse("__app__:edit", args=[record.pk]), {"title": "Renamed"})
    client.post(reverse("__app__:comment", args=[record.pk]), {"message": "Looks good"})
    client.post(reverse("__app__:transition", args=[record.pk]), {"to_status": "done"})
    record.refresh_from_db()
    assert (record.title, record.status) == ("Renamed", "done")
    kinds = list(record.events.values_list("kind", flat=True))
    assert kinds == ["status_changed", "comment", "updated", "created"]
    assert client.get(record.get_absolute_url()).status_code == 200
    listed = client.get(reverse("__app__:list"), {"q": "Renamed", "status": "done"})
    assert list(listed.context["records"]) == [record]


def test_illegal_transition_is_rejected(client, editor, record):
    client.force_login(editor)
    client.post(reverse("__app__:transition", args=[record.pk]), {"to_status": "bogus"})
    record.refresh_from_db()
    assert record.status == __Model__.Status.OPEN
