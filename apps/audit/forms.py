from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


class AuditFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    action = forms.ChoiceField(
        required=False, choices=[("", "Any action"), *AuditLog.Action.choices]
    )
    content_type = forms.ModelChoiceField(
        required=False,
        queryset=ContentType.objects.order_by("app_label", "model"),
        empty_label="Any record type",
    )
    object_id = forms.CharField(required=False, label="Record ID")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            is_select = isinstance(field.widget, forms.Select)
            field.widget.attrs.setdefault("class", "form-select" if is_select else "form-control")

    def filter(self, qs):
        if not self.is_valid():
            return qs.none()
        d = self.cleaned_data
        if d["q"]:
            q = d["q"].strip()
            qs = (
                qs.filter(actor_label__icontains=q)
                | qs.filter(object_repr__icontains=q)
                | (qs.filter(request_id=q))
            )
        if d["action"]:
            qs = qs.filter(action=d["action"])
        if d["content_type"]:
            qs = qs.filter(content_type=d["content_type"])
        if d["object_id"]:
            qs = qs.filter(object_id=d["object_id"])
        if d["date_from"]:
            qs = qs.filter(created_at__date__gte=d["date_from"])
        if d["date_to"]:
            qs = qs.filter(created_at__date__lte=d["date_to"])
        return qs
