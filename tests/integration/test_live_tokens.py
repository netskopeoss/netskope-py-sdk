"""Live integration tests for the API Token Management API.

Follows the safety checklist in ``tests/integration/conftest.py``: test
objects use the ``sdk-inttest-`` prefix, every create has a guaranteed
delete, and unavailable APIs skip rather than fail.

SECURITY: the token secret returned by ``create()`` is never printed,
logged, or placed in an assertion whose failure message could reproduce it —
assertions are made on pre-computed booleans only.

``client.tokens`` is not wired on the client yet, so the resource is
instantiated directly on the client transport.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.models.tokens import ApiToken
from netskope.resources.tokens import TokensResource

from .conftest import skip_if_unavailable, unique_name

# Minimal read-only scope for the write-cycle token (events endpoint).
_MINIMAL_SCOPE = [{"endpoint": "/api/v2/events", "permissions": "r"}]


@pytest.fixture
def tokens(client: NetskopeClient) -> TokensResource:
    return TokensResource(client._transport)


@pytest.mark.integration
class TestTokensIntegration:
    """Live tests for API token management."""

    def test_list_tokens(self, tokens: TokensResource) -> None:
        """Read smoke: listing tokens succeeds, yields typed models, no secrets."""
        try:
            result = tokens.list()
        except APIError as e:
            skip_if_unavailable(e, "API tokens")
        else:
            assert isinstance(result, list)
            for token in result:
                assert isinstance(token, ApiToken)
                assert token.token is None  # secrets are never listed

    def test_token_write_cycle(self, tokens: TokensResource) -> None:
        """Create -> assert secret presence (never its value) -> list -> delete."""
        name = unique_name("token")
        expires = datetime.now(tz=UTC) + timedelta(hours=1)
        try:
            created = tokens.create(name, _MINIMAL_SCOPE, expires=expires)
        except APIError as e:
            skip_if_unavailable(e, "API tokens")
            return
        assert created.id is not None
        try:
            # The secret must be present in the create response.  Assert only
            # on pre-computed booleans so no failure message can leak it.
            secret_present = bool(created.token)
            secret_is_str = isinstance(created.token, str)
            assert secret_present, "create() response did not include a token secret"
            assert secret_is_str, "token secret is not a string"

            listed = tokens.list()
            listed_ids = [t.id for t in listed]
            assert created.id in listed_ids
            match = next(t for t in listed if t.id == created.id)
            assert match.name == name
            assert match.token is None  # list never returns secrets

            fetched = tokens.get(created.id)
            assert fetched.id == created.id
            assert fetched.name == name
            assert fetched.token is None  # get never returns the secret
        finally:
            with contextlib.suppress(NotFoundError, APIError):
                tokens.delete(created.id)
