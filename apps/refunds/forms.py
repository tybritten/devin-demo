from django import forms

from .models import Refund


class RefundForm(forms.ModelForm):
    class Meta:
        model = Refund
        fields = ["customer_name", "customer_ref", "order_ref", "amount", "reason", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class RefundFilterForm(forms.Form):
    q = forms.CharField(required=False)
    reason = forms.ChoiceField(required=False, choices=[("", "Any reason"), *Refund.Reason.choices])


class TransitionForm(forms.Form):
    to_status = forms.ChoiceField(label="Move to")
    payment_reference = forms.CharField(
        required=False, max_length=100, help_text="Required when marking as Paid."
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required for Rejected and Cancelled.",
    )

    def __init__(self, *args, statuses=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["to_status"].choices = [(s.value, s.label) for s in statuses]
        if Refund.Status.PAID not in statuses:
            del self.fields["payment_reference"]


class CommentForm(forms.Form):
    message = forms.CharField(label="Add a comment", widget=forms.Textarea(attrs={"rows": 2}))
