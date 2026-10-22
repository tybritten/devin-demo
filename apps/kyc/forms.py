from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db.models import Q

from .models import CaseDocument, Customer, ReviewCase

ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "tif", "tiff", "heic", "docx"]
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class DateInput(forms.DateInput):
    input_type = "date"


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "legal_name",
            "external_ref",
            "email",
            "date_of_birth",
            "country",
        ]
        widgets = {"date_of_birth": DateInput()}

    def clean_country(self):
        return self.cleaned_data["country"].upper()


class CaseForm(forms.ModelForm):
    class Meta:
        model = ReviewCase
        fields = ["review_type", "risk_rating", "due_date", "summary"]
        widgets = {"due_date": DateInput(), "summary": forms.Textarea(attrs={"rows": 3})}


class QueueFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"placeholder": "Name, reference or external ref"}),
    )
    status = forms.ChoiceField(
        required=False, choices=[("", "Any status"), *ReviewCase.Status.choices]
    )
    risk = forms.ChoiceField(required=False, choices=[("", "Any risk"), *ReviewCase.Risk.choices])


def kyc_staff():
    User = get_user_model()
    perm = Q(
        groups__permissions__codename="view_reviewcase",
        groups__permissions__content_type__app_label="kyc",
    ) | Q(
        user_permissions__codename="view_reviewcase",
        user_permissions__content_type__app_label="kyc",
    )
    return (
        User.objects.filter(is_active=True)
        .filter(perm | Q(is_superuser=True))
        .distinct()
        .order_by("first_name", "last_name", "username")
    )


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


class AssignForm(forms.Form):
    assignee = UserChoiceField(queryset=None, required=False, empty_label="Unassigned")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = kyc_staff()


class TransitionForm(forms.Form):
    to_status = forms.ChoiceField(label="Move to")
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required for Pending info, Escalated and Rejected.",
    )

    def __init__(self, *args, statuses=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to_status"].choices = [(s.value, s.label) for s in statuses]


class CommentForm(forms.Form):
    message = forms.CharField(label="Add a comment", widget=forms.Textarea(attrs={"rows": 2}))


class DocumentForm(forms.ModelForm):
    class Meta:
        model = CaseDocument
        fields = ["document_type", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].validators.append(FileExtensionValidator(ALLOWED_UPLOAD_EXTENSIONS))

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("File is larger than 20 MB.")
        return f
