from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def person(user, default="—"):
    if user is None:
        return default
    return user.get_full_name() or user.username


@register.simple_tag
def badge(label, css="text-bg-secondary"):
    return format_html('<span class="badge {}">{}</span>', css, label)
