import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.urls import reverse

from apps.core.tests.factories import UserFactory
from apps.core.users import deactivate
from apps.kyc import services
from apps.kyc.forms import kyc_staff as assignable_users
from apps.kyc.roles import REVIEWER_GROUP
from apps.kyc.tests.factories import ReviewCaseFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def reviewer():
    user = UserFactory(username="rev")
    user.groups.add(Group.objects.get(name=REVIEWER_GROUP))
    return user


def test_users_cannot_be_deleted_and_keep_their_assignments(reviewer):
    case = ReviewCaseFactory(assigned_to=reviewer)
    for attempt in (reviewer.delete, User.objects.filter(pk=reviewer.pk).delete):
        with pytest.raises(ProtectedError), transaction.atomic():
            attempt()
    case.refresh_from_db()
    assert case.assigned_to == reviewer


def test_deactivated_user_is_signed_out_and_unassignable(client, reviewer):
    client.force_login(reviewer)
    assert client.get(reverse("kyc:queue")).status_code == 200
    assert reviewer in assignable_users()
    deactivate([reviewer])
    reviewer.refresh_from_db()
    assert client.get(reverse("kyc:queue")).status_code == 302
    assert not client.login(username="rev", password="pw")
    assert reviewer not in assignable_users()
    with pytest.raises(ValidationError):
        services.assign(ReviewCaseFactory(), assignee=reviewer, actor=reviewer)


def test_admin_offers_deactivate_instead_of_delete(admin_client, reviewer):
    changelist = reverse("admin:auth_user_changelist")
    actions = admin_client.get(changelist).context["action_form"].fields["action"].choices
    names = [name for name, _ in actions]
    assert "deactivate_users" in names and "delete_selected" not in names
    assert (
        admin_client.get(reverse("admin:auth_user_delete", args=[reviewer.pk])).status_code == 403
    )
    admin_client.post(changelist, {"action": "deactivate_users", "_selected_action": [reviewer.pk]})
    reviewer.refresh_from_db()
    assert not reviewer.is_active
