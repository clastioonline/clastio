from types import SimpleNamespace
import pytest
from app.services.clerk_roles import apply_clerk_role


@pytest.mark.parametrize("info,expected", [
    ({"public_metadata": {"role": "admin", "admin_role": "super_admin"}}, ("admin", "super_admin")),
    ({"public_metadata": {"role": "admin"}}, ("admin", "admin")),
    ({"unsafe_metadata": {"role": "admin"}}, ("teacher", None)),
    ({"public_metadata": {"role": "admin", "admin_role": "unknown"}}, ("teacher", None)),
    ({}, ("teacher", None)),
])
def test_clerk_roles_replace_existing_privileges(info, expected):
    user = SimpleNamespace(role="admin", admin_role="super_admin")
    apply_clerk_role(user, info)
    assert (user.role, user.admin_role) == expected
