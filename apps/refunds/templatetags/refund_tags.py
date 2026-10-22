from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.html import format_html

register = template.Library()

STATUS_CLASSES = {
    "requested": "text-bg-primary",
    "approved": "text-bg-info",
    "paid": "text-bg-success",
    "rejected": "text-bg-dark",
    "cancelled": "text-bg-secondary",
}


@register.simple_tag
def refund_status_badge(refund):
    return format_html(
        '<span class="badge {}">{}</span>',
        STATUS_CLASSES.get(refund.status, "text-bg-secondary"),
        refund.get_status_display(),
    )


@register.filter
def money(value):
    value = value or 0
    return f"{settings.REFUND_CURRENCY} {intcomma(f'{value:.2f}')}"
