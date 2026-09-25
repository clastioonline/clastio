"""Staff roles and permissions. Every privileged endpoint checks a permission server-side (see deps.require)."""

from __future__ import annotations

PERMISSIONS = {
    "users.view": "See teacher accounts, plans, usage and activity (metadata only)",
    "users.manage": "Suspend, restore, force logout, reset verification, add notes",
    "users.ban": "Ban accounts and approve account deletion",
    "users.content": "Open teacher-created content (lessons, documents, media)",
    "billing.view": "See subscriptions, payments and invoices",
    "billing.modify": "Change plans, grant or revoke credits, edit prices and trials",
    "analytics.view": "Dashboards and product analytics",
    "api_usage.view": "API requests, AI usage and costs",
    "audit.view": "Admin audit log",
    "security.view": "Security events and sessions",
    "system.logs.view": "Jobs, webhooks, emails, system log and request traces",
    "settings.modify": "System settings, feature flags, maintenance mode, AI routing",
    "support.manage": "Support tickets and feature requests",
    "announcements.manage": "Publish announcements",
    "legal.manage": "Publish legal document versions",
    "data.export": "Export admin datasets",
    "admins.manage": "Grant or remove staff roles",
}

ALL = set(PERMISSIONS)

ROLES: dict[str, set[str]] = {
    "super_admin": ALL,
    "admin": ALL - {"admins.manage"},
    "support": {"users.view", "users.manage", "support.manage", "billing.view", "security.view", "system.logs.view"},
    "analyst": {"analytics.view", "api_usage.view", "users.view", "data.export"},
    "finance": {"billing.view", "billing.modify", "analytics.view", "users.view", "data.export"},
    "moderator": {"users.view", "users.manage", "users.ban", "users.content", "security.view", "support.manage"},
}

ROLE_LABELS = {"super_admin": "Super admin", "admin": "Admin", "support": "Support", "analyst": "Analyst",
               "finance": "Finance", "moderator": "Moderator"}


def permissions_for(role: str | None, admin_role: str | None) -> set[str]:
    if role != "admin":
        return set()
    # A staff account without a specific staff role gets the standard admin set (never admins.manage).
    return ROLES.get(admin_role or "admin", set())
