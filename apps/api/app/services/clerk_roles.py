"""Staff privileges derive only from server-managed Clerk metadata."""
from app.core.permissions import ROLES


def apply_clerk_role(user, info: dict) -> None:
    metadata = info.get("public_metadata") or {}
    role = metadata.get("role")
    staff_role = metadata.get("admin_role", "admin")
    if role == "admin" and isinstance(staff_role, str) and staff_role in ROLES:
        user.role, user.admin_role = "admin", staff_role
    else:
        user.role, user.admin_role = "teacher", None
