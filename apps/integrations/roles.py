"""Default groups for integrations. Synced after every `migrate`.

Systems are registered and edited in the Django admin, so admins also need `is_staff`.
"""

VIEWER_GROUP = "Integrations Viewer"
ADMIN_GROUP = "Integrations Admin"

VIEWER_PERMS = ["view_externalsystem", "view_syncrun"]
ROLES = {
    VIEWER_GROUP: VIEWER_PERMS,
    ADMIN_GROUP: [*VIEWER_PERMS, "add_externalsystem", "change_externalsystem"],
}
