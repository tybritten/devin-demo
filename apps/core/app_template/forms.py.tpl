from django import forms

from apps.core.forms import UserChoiceField, users_with_perm

from .models import __Model__


class __Model__Form(forms.ModelForm):
    owner = UserChoiceField(queryset=None, required=False)

    class Meta:
        model = __Model__
        fields = ["title", "description", "owner"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = users_with_perm("__app__", "change___model__")


class FilterForm(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(
        required=False, choices=[("", "Any status"), *__Model__.Status.choices]
    )


class TransitionForm(forms.Form):
    to_status = forms.ChoiceField(label="Move to")
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to_status"].choices = choices


class CommentForm(forms.Form):
    message = forms.CharField(
        label="", widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Add a comment"})
    )
