from django.db.models import Count, Q

from .models import FeatureFlag


def tile(user):
    if not user.has_perm("flags.view_featureflag"):
        return None
    counts = FeatureFlag.objects.filter(is_archived=False).aggregate(
        on=Count("pk", filter=Q(enabled=True, rollout_percentage__gte=100)),
        partial=Count("pk", filter=Q(enabled=True, rollout_percentage__lt=100)),
        off=Count("pk", filter=Q(enabled=False)),
    )
    return {
        "title": "Feature Flags",
        "description": "Turn product features on, off, or roll them out gradually.",
        "url_name": "flags:flag_list",
        "stats": [("On", counts["on"]), ("Partial", counts["partial"]), ("Off", counts["off"])],
    }
