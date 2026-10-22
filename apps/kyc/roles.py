"""Default groups for the KYC app. Synced after every `migrate` so they stay in step with code."""

from apps.core.roles import sync_roles

REVIEWER_GROUP = "KYC Reviewer"
APPROVER_GROUP = "KYC Approver"

REVIEWER_PERMS = [
    "view_customer",
    "add_customer",
    "change_customer",
    "view_reviewcase",
    "add_reviewcase",
    "change_reviewcase",
    "view_casedocument",
    "add_casedocument",
]
APPROVER_PERMS = [*REVIEWER_PERMS, "decide_case", "approve_high_risk"]

ROLES = {REVIEWER_GROUP: REVIEWER_PERMS, APPROVER_GROUP: APPROVER_PERMS}


def ensure_roles(**kwargs):
    sync_roles("kyc", ROLES)
