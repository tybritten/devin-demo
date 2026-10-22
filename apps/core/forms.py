from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q


def users_with_perm(app_label, codename):
    """Active users holding `app_label.codename` directly, via a group, or as superuser."""
    perm = Q(
        groups__permissions__codename=codename,
        groups__permissions__content_type__app_label=app_label,
    ) | Q(
        user_permissions__codename=codename,
        user_permissions__content_type__app_label=app_label,
    )
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(perm | Q(is_superuser=True))
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


class DateInput(forms.DateInput):
    input_type = "date"
