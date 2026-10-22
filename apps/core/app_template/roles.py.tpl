"""Default groups for __Title__. Synced after every `migrate` by OpsAppConfig."""

VIEWER_GROUP = "__Title__ Viewer"
EDITOR_GROUP = "__Title__ Editor"

VIEWER_PERMS = ["view___model__", "view___model__event"]
ROLES = {
    VIEWER_GROUP: VIEWER_PERMS,
    EDITOR_GROUP: [*VIEWER_PERMS, "add___model__", "change___model__"],
}
