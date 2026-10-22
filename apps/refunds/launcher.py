from django.db.models import Sum

from .models import Refund
from .templatetags.refund_tags import money


def tile(user):
    if not user.has_perm("refunds.view_refund"):
        return None
    pending = Refund.objects.pending()
    return {
        "title": "Refunds",
        "description": "Request, approve and track customer refunds.",
        "url_name": "refunds:dashboard",
        "stats": [
            ("Pending approval", pending.count()),
            ("Awaiting payment", Refund.objects.awaiting_payment().count()),
            ("Pending value", money(pending.aggregate(t=Sum("amount"))["t"])),
        ],
    }
