from .models import ReviewCase


def tile(user):
    if not user.has_perm("kyc.view_reviewcase"):
        return None
    open_cases = ReviewCase.objects.open()
    return {
        "title": "KYC Review Queue",
        "description": "Review and decide customer KYC cases.",
        "url_name": "kyc:queue",
        "stats": [
            ("Assigned to me", open_cases.filter(assigned_to=user).count()),
            ("Unassigned", open_cases.filter(assigned_to__isnull=True).count()),
            ("Overdue", open_cases.overdue().count()),
        ],
    }
