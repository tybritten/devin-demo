from django import template
from django.utils.html import format_html

from apps.core.templatetags.ui_tags import person

register = template.Library()

STATUS_CLASSES = {
    "new": "text-bg-primary",
    "in_review": "text-bg-info",
    "pending_info": "text-bg-warning",
    "escalated": "text-bg-danger",
    "approved": "text-bg-success",
    "rejected": "text-bg-dark",
}
RISK_CLASSES = {
    "low": "text-bg-light border",
    "medium": "text-bg-warning",
    "high": "text-bg-danger",
}


@register.simple_tag
def status_badge(case):
    return format_html(
        '<span class="badge {}">{}</span>',
        STATUS_CLASSES.get(case.status, "text-bg-secondary"),
        case.get_status_display(),
    )


@register.simple_tag
def risk_badge(case):
    return format_html(
        '<span class="badge {}">{}</span>',
        RISK_CLASSES.get(case.risk_rating, "text-bg-secondary"),
        case.get_risk_rating_display(),
    )


register.filter("person", person)
