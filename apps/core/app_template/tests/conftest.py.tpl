import pytest
from django.contrib.auth.models import Group

from apps.__app__.roles import EDITOR_GROUP, VIEWER_GROUP
from apps.core.tests.factories import UserFactory


@pytest.fixture
def viewer(db):
    user = UserFactory(username="__app___viewer")
    user.groups.add(Group.objects.get(name=VIEWER_GROUP))
    return user


@pytest.fixture
def editor(db):
    user = UserFactory(username="__app___editor")
    user.groups.add(Group.objects.get(name=EDITOR_GROUP))
    return user
