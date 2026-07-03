"""Live integration tests for the User Management (read) API.

Read-only coverage per the safety checklist in ``tests/integration/conftest.py``:
no create/update/delete calls are made — this namespace is query-only.
Credentials come from environment variables only (see the shared ``client``
fixture).

Run with: pytest tests/integration/test_live_users.py -m integration -v
"""

from __future__ import annotations

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError
from netskope.models.users import UmGroup, UmUser
from netskope.resources.users import UsersResource

from .conftest import skip_if_unavailable


@pytest.mark.integration
class TestUsersIntegration:
    """Live, read-only tests for the User Management query API."""

    def test_list_users(self, client: NetskopeClient) -> None:
        """List users (capped at 5) and get typed responses."""
        users_resource = UsersResource(client._transport)
        try:
            users = users_resource.list(limit=5)
        except APIError as exc:
            skip_if_unavailable(exc, "User Management API")
            return
        assert isinstance(users, list)
        assert len(users) <= 5
        if users:
            assert isinstance(users[0], UmUser)
            assert users[0].id is not None

    def test_list_groups(self, client: NetskopeClient) -> None:
        """List groups (capped at 5) and get typed responses."""
        users_resource = UsersResource(client._transport)
        try:
            groups = users_resource.groups.list(limit=5)
        except APIError as exc:
            skip_if_unavailable(exc, "User Management groups API")
            return
        assert isinstance(groups, list)
        assert len(groups) <= 5
        if groups:
            assert isinstance(groups[0], UmGroup)

    def test_get_user_by_email_round_trip(self, client: NetskopeClient) -> None:
        """If any user exists, looking it up by primary email round-trips."""
        users_resource = UsersResource(client._transport)
        try:
            users = users_resource.list(limit=5)
        except APIError as exc:
            skip_if_unavailable(exc, "User Management API")
            return
        email = next((u.primary_email for u in users if u.primary_email), None)
        if email is None:
            pytest.skip("No user with an email address available on this tenant")
        try:
            user = users_resource.get(email)
        except APIError as exc:
            skip_if_unavailable(exc, "User Management API")
            return
        assert user is not None
        assert user.primary_email == email
