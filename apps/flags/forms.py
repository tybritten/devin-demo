import re

from django import forms

from apps.core.forms import UserChoiceField, users_with_perm

from .models import FeatureFlag


class TargetsField(forms.CharField):
    """One target ID per line (commas also accepted)."""

    widget = forms.Textarea(attrs={"rows": 3, "placeholder": "user-123\ncustomer-456"})

    def prepare_value(self, value):
        return "\n".join(value) if isinstance(value, list) else value

    def to_python(self, value):
        items = (t.strip() for t in re.split(r"[\n,]", value or ""))
        return list(dict.fromkeys(t for t in items if t))


class FlagForm(forms.ModelForm):
    targets = TargetsField(
        required=False, help_text=FeatureFlag._meta.get_field("targets").help_text
    )
    owner = UserChoiceField(queryset=None, required=False, empty_label="No owner")
    comment = forms.CharField(
        required=False, help_text="Why are you making this change? Saved in the history."
    )

    class Meta:
        model = FeatureFlag
        fields = ["key", "name", "description", "owner", "enabled", "rollout_percentage", "targets"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "rollout_percentage": forms.NumberInput(attrs={"min": 0, "max": 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = users_with_perm("flags", "view_featureflag")
        if self.instance.pk:
            del self.fields["key"]


class FlagFilterForm(forms.Form):
    STATES = [
        ("", "Active flags"),
        ("on", "On"),
        ("partial", "Partial"),
        ("off", "Off"),
        ("archived", "Archived"),
    ]
    q = forms.CharField(required=False)
    state = forms.ChoiceField(required=False, choices=STATES)


class CommentOnlyForm(forms.Form):
    comment = forms.CharField(required=False)
