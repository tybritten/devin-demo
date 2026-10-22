"""Default groups for the refunds app. Synced after every `migrate`."""

from apps.core.roles import sync_roles

REQUESTER_GROUP = "Refunds Requester"
APPROVER_GROUP = "Refunds Approver"
SENIOR_APPROVER_GROUP = "Refunds Senior Approver"
FINANCE_GROUP = "Refunds Finance"

BASE_PERMS = ["view_refund", "change_refund"]
ROLES = {
    REQUESTER_GROUP: [*BASE_PERMS, "add_refund"],
    APPROVER_GROUP: [*BASE_PERMS, "approve_refund"],
    SENIOR_APPROVER_GROUP: [*BASE_PERMS, "approve_refund", "approve_over_limit"],
    FINANCE_GROUP: [*BASE_PERMS, "mark_paid"],
}


def ensure_roles(**kwargs):
    sync_roles("refunds", ROLES)
