"""Lock an account out of password login after repeated failures, using the audit log as state."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .log import Action, record
from .models import AuditLog


def is_locked_out(username):
    since = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    # Attempts rejected by the lockout itself don't count, so the lock always expires on time.
    failures = AuditLog.objects.filter(
        action=Action.LOGIN_FAILED, changes__username=username, created_at__gte=since
    ).exclude(changes__contains={"reason": "locked_out"})
    return failures.count() >= settings.LOGIN_LOCKOUT_ATTEMPTS


class LockoutAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "locked_out": "Too many failed sign-in attempts. Try again in %(minutes)s minutes.",
    }

    def clean(self):
        username = (self.cleaned_data.get("username") or "")[:150]
        if username and is_locked_out(username):
            record(
                Action.LOGIN_FAILED,
                actor=None,
                request=self.request,
                changes={"username": username, "reason": "locked_out"},
            )
            raise ValidationError(
                self.error_messages["locked_out"],
                code="locked_out",
                params={"minutes": settings.LOGIN_LOCKOUT_MINUTES},
            )
        return super().clean()
