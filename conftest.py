import pytest
from django.contrib.auth.models import Group

from apps.kyc.roles import APPROVER_GROUP, REVIEWER_GROUP
from apps.kyc.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


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
