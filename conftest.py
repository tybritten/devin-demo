import pytest
from django.contrib.auth.models import Group

from apps.core.tests.factories import UserFactory
from apps.kyc.roles import APPROVER_GROUP, REVIEWER_GROUP


@pytest.fixture(autouse=True)
def _test_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def reviewer(db):
    user = UserFactory(username="reviewer")
    user.groups.add(Group.objects.get(name=REVIEWER_GROUP))
    return user


@pytest.fixture
def approver(db):
    user = UserFactory(username="approver")
    user.groups.add(Group.objects.get(name=APPROVER_GROUP))
    return user


@pytest.fixture
def outsider(db):
    return UserFactory(username="outsider")


def _user_in(username, *groups):
    user = UserFactory(username=username)
    user.groups.add(*Group.objects.filter(name__in=groups))
    return user


@pytest.fixture
def refund_requester(db):
    from apps.refunds.roles import REQUESTER_GROUP

    return _user_in("requester", REQUESTER_GROUP)


@pytest.fixture
def refund_approver(db):
    from apps.refunds.roles import APPROVER_GROUP

    return _user_in("refund_approver", APPROVER_GROUP)


@pytest.fixture
def refund_senior(db):
    from apps.refunds.roles import SENIOR_APPROVER_GROUP

    return _user_in("refund_senior", SENIOR_APPROVER_GROUP)


@pytest.fixture
def refund_finance(db):
    from apps.refunds.roles import FINANCE_GROUP

    return _user_in("refund_finance", FINANCE_GROUP)


@pytest.fixture
def flag_viewer(db):
    from apps.flags.roles import VIEWER_GROUP

    return _user_in("flag_viewer", VIEWER_GROUP)


@pytest.fixture
def flag_editor(db):
    from apps.flags.roles import EDITOR_GROUP

    return _user_in("flag_editor", EDITOR_GROUP)
