"""Live integration tests for the RBAC API (roles + admin users).

Exercises a full roles write cycle (create -> get -> update -> delete) on a
uniquely named custom role granting no permissions (empty ``apiGroups``), per
the safety checklist in ``tests/integration/conftest.py``.  The admin-users
read smoke is bounded to a handful of results.  Credentials come from
environment variables only.

``client.rbac`` is not wired into the client yet, so the resource is
instantiated directly against the client's transport.

Run with: pytest tests/integration/test_live_rbac.py -m integration -v
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.rbac import RbacRole
from netskope.models.scim import ScimUser
from netskope.resources.rbac import RbacResource

from .conftest import skip_if_unavailable, unique_name


@pytest.mark.integration
class TestRbacRolesIntegration:
    """Live tests for the RBAC roles API."""

    def test_list_roles(self, client: NetskopeClient) -> None:
        """List roles and get typed responses."""
        rbac = RbacResource(client._transport)
        try:
            roles = rbac.roles.list(limit=10)
        except APIError as exc:
            skip_if_unavailable(exc, "RBAC roles API")
            return
        assert isinstance(roles, list)
        if roles:
            assert isinstance(roles[0], RbacRole)

    def test_write_cycle(self, client: NetskopeClient) -> None:
        """Create a no-permission custom role, read it back, rename it, delete it."""
        rbac = RbacResource(client._transport)
        name = unique_name("rbacrole")

        try:
            created = rbac.roles.create(
                name,
                description="SDK integration test role (safe to delete)",
                api_groups=[],
            )
        except APIError as exc:
            skip_if_unavailable(exc, "RBAC roles API")
            return

        role_id = created.id
        assert role_id is not None
        try:
            assert created.name == name

            fetched = rbac.roles.get(role_id)
            assert fetched.id == role_id
            assert fetched.name == name

            new_name = unique_name("rbacrole")
            updated = rbac.roles.update(role_id, name=new_name)
            assert updated.name == new_name
        finally:
            # Already gone or delete unavailable — never fail teardown.
            with contextlib.suppress(APIError):
                rbac.roles.delete(role_id)


@pytest.mark.integration
class TestRbacAdminsIntegration:
    """Live tests for the RBAC admin-users (SCIM) API."""

    def test_list_admins(self, client: NetskopeClient) -> None:
        """List a bounded page of admin users and get typed responses."""
        rbac = RbacResource(client._transport)
        try:
            admins: list[ScimUser] = []
            for admin in rbac.admins.list(page_size=10):
                admins.append(admin)
                if len(admins) >= 10:
                    break
        except APIError as exc:
            skip_if_unavailable(exc, "RBAC admin users API")
            return
        if admins:
            assert isinstance(admins[0], ScimUser)
