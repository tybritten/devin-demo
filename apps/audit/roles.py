"""Default groups for the audit log. Synced after every `migrate` by OpsAppConfig."""

AUDITOR_GROUP = "Auditor"

ROLES = {AUDITOR_GROUP: ["view_auditlog"]}
