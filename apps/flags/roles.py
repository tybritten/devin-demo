"""Default groups for the feature-flag app. Synced after every `migrate`."""

from apps.core.roles import sync_roles

VIEWER_GROUP = "Flags Viewer"
EDITOR_GROUP = "Flags Editor"

VIEWER_PERMS = ["view_featureflag", "view_flagchange"]
ROLES = {
    VIEWER_GROUP: VIEWER_PERMS,
    EDITOR_GROUP: [*VIEWER_PERMS, "add_featureflag", "change_featureflag"],
}


def ensure_roles(**kwargs):
    sync_roles("flags", ROLES)
