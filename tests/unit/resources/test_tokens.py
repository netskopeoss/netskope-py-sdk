"""Tests for the API Tokens resource with mocked HTTP.

``client.tokens`` is not wired on the client yet, so tests instantiate
``TokensResource`` / ``AsyncTokensResource`` directly on the client transport.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.tokens import ApiToken, ApiTokenEndpoint
from netskope.resources.tokens import AsyncTokensResource, TokensResource
from tests.unit.resources.conftest import sent_json

_URL = "https://t.goskope.com/api/v2/auth/tokens"

_EXPIRES = 2147384600

_TOKEN_READ = {
    "id": "tok-1",
    "name": "ci-token",
    "expires": _EXPIRES,
    "endpoints": [{"endpoint": "/api/v2/events", "permissions": "r"}],
}

# Create/reissue responses additionally carry the one-time secret.
_TOKEN_CREATED = {**_TOKEN_READ, "token": "s3cret-value"}

# Per the gateway spec, list returns a bare JSON array (no envelope).
_LIST_BODY = [_TOKEN_READ]


@pytest.fixture
def tokens(client: NetskopeClient) -> TokensResource:
    return TokensResource(client._transport)


@pytest.fixture
def atokens(aclient: AsyncNetskopeClient) -> AsyncTokensResource:
    return AsyncTokensResource(aclient._transport)


class TestTokensResource:
    """Tests for the sync TokensResource."""

    @respx.mock
    def test_list_bare_array_envelope(self, tokens: TokensResource) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        result = tokens.list()
        assert route.called
        assert len(result) == 1
        assert isinstance(result[0], ApiToken)
        assert result[0].id == "tok-1"
        assert result[0].name == "ci-token"
        assert result[0].expires == _EXPIRES
        assert result[0].endpoints[0] == ApiTokenEndpoint(
            endpoint="/api/v2/events", permissions="r"
        )
        assert result[0].token is None

    @respx.mock
    def test_list_fields_param(self, tokens: TokensResource) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json=[]))
        assert tokens.list(fields=["id", "name", "expires"]) == []
        assert route.calls.last.request.url.params["fields"] == "id,name,expires"

    @respx.mock
    def test_get(self, tokens: TokensResource) -> None:
        route = respx.get(f"{_URL}/tok-1").mock(return_value=httpx.Response(200, json=_TOKEN_READ))
        token = tokens.get("tok-1")
        assert route.called
        assert token.id == "tok-1"
        assert token.token is None

    @respx.mock
    def test_get_rejects_unsafe_id(self, tokens: TokensResource) -> None:
        with pytest.raises(ValidationError, match="token_id"):
            tokens.get("../etc")
        assert len(respx.calls) == 0

    @respx.mock
    def test_create_body_exact(self, tokens: TokensResource) -> None:
        """create() must send name, epoch expires, and spec-shaped endpoint objects."""
        route = respx.post(_URL).mock(return_value=httpx.Response(201, json=_TOKEN_CREATED))
        token = tokens.create(
            "ci-token",
            [
                "/api/v2/events",  # bare string defaults to read-only
                {"endpoint": "/api/v2/alerts", "permissions": "rw"},
                ApiTokenEndpoint(endpoint="/api/v2/policy/urllist", permissions="r"),
            ],
            expires=_EXPIRES,
        )
        assert sent_json(route) == {
            "name": "ci-token",
            "expires": _EXPIRES,
            "endpoints": [
                {"endpoint": "/api/v2/events", "permissions": "r"},
                {"endpoint": "/api/v2/alerts", "permissions": "rw"},
                {"endpoint": "/api/v2/policy/urllist", "permissions": "r"},
            ],
        }
        assert isinstance(token, ApiToken)
        assert token.token == "s3cret-value"

    @respx.mock
    def test_create_datetime_expires_converted_to_epoch(self, tokens: TokensResource) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(201, json=_TOKEN_CREATED))
        expires_at = datetime(2038, 1, 18, tzinfo=UTC)
        tokens.create("ci-token", ["/api/v2/events"], expires=expires_at)
        assert sent_json(route)["expires"] == int(expires_at.timestamp())

    @respx.mock
    def test_create_invalid_permissions_no_http(self, tokens: TokensResource) -> None:
        with pytest.raises(ValidationError, match="permissions"):
            tokens.create(
                "bad",
                [{"endpoint": "/api/v2/events", "permissions": "admin"}],
                expires=_EXPIRES,
            )
        assert len(respx.calls) == 0

    @respx.mock
    def test_create_empty_endpoints_no_http(self, tokens: TokensResource) -> None:
        with pytest.raises(ValidationError, match="endpoint"):
            tokens.create("bad", [], expires=_EXPIRES)
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_is_patch_with_given_fields(self, tokens: TokensResource) -> None:
        route = respx.patch(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json=_TOKEN_READ)
        )
        token = tokens.update(
            "tok-1",
            name="renamed",
            expires=_EXPIRES,
            endpoints=[{"endpoint": "/api/v2/events", "permissions": "rw"}],
        )
        assert isinstance(token, ApiToken)
        assert sent_json(route) == {
            "name": "renamed",
            "expires": _EXPIRES,
            "endpoints": [{"endpoint": "/api/v2/events", "permissions": "rw"}],
        }

    @respx.mock
    def test_update_nothing_to_update_no_http(self, tokens: TokensResource) -> None:
        with pytest.raises(ValidationError, match="Nothing to update"):
            tokens.update("tok-1")
        assert len(respx.calls) == 0

    @respx.mock
    def test_reissue_sends_operation_and_returns_secret(self, tokens: TokensResource) -> None:
        route = respx.patch(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json=_TOKEN_CREATED)
        )
        token = tokens.reissue("tok-1")
        assert sent_json(route) == {"operation": "reissue"}
        assert token.token == "s3cret-value"

    @respx.mock
    def test_delete(self, tokens: TokensResource) -> None:
        route = respx.delete(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        assert tokens.delete("tok-1") is None
        assert route.called

    @respx.mock
    def test_revoke_is_delete_alias(self, tokens: TokensResource) -> None:
        route = respx.delete(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        assert TokensResource.revoke is TokensResource.delete
        assert tokens.revoke("tok-1") is None
        assert route.called


class TestAsyncTokensResource:
    """Tests for the async AsyncTokensResource."""

    @respx.mock
    async def test_list(self, atokens: AsyncTokensResource) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json=_LIST_BODY))
        result = await atokens.list()
        assert len(result) == 1
        assert isinstance(result[0], ApiToken)
        assert result[0].token is None

    @respx.mock
    async def test_get(self, atokens: AsyncTokensResource) -> None:
        respx.get(f"{_URL}/tok-1").mock(return_value=httpx.Response(200, json=_TOKEN_READ))
        token = await atokens.get("tok-1")
        assert token.id == "tok-1"

    @respx.mock
    async def test_create_body_exact(self, atokens: AsyncTokensResource) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(201, json=_TOKEN_CREATED))
        token = await atokens.create("ci-token", ["/api/v2/events"], expires=_EXPIRES)
        assert sent_json(route) == {
            "name": "ci-token",
            "expires": _EXPIRES,
            "endpoints": [{"endpoint": "/api/v2/events", "permissions": "r"}],
        }
        assert token.token == "s3cret-value"

    @respx.mock
    async def test_create_invalid_permissions_no_http(self, atokens: AsyncTokensResource) -> None:
        with pytest.raises(ValidationError, match="permissions"):
            await atokens.create(
                "bad", [{"endpoint": "/api/v2/events", "permissions": "x"}], expires=_EXPIRES
            )
        assert len(respx.calls) == 0

    @respx.mock
    async def test_update_is_patch(self, atokens: AsyncTokensResource) -> None:
        route = respx.patch(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json=_TOKEN_READ)
        )
        await atokens.update("tok-1", name="renamed")
        assert sent_json(route) == {"name": "renamed"}

    @respx.mock
    async def test_reissue(self, atokens: AsyncTokensResource) -> None:
        route = respx.patch(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json=_TOKEN_CREATED)
        )
        token = await atokens.reissue("tok-1")
        assert sent_json(route) == {"operation": "reissue"}
        assert token.token == "s3cret-value"

    @respx.mock
    async def test_delete_and_revoke_alias(self, atokens: AsyncTokensResource) -> None:
        route = respx.delete(f"{_URL}/tok-1").mock(
            return_value=httpx.Response(200, json={"id": "tok-1", "name": "ci-token"})
        )
        assert AsyncTokensResource.revoke is AsyncTokensResource.delete
        assert await atokens.delete("tok-1") is None
        assert route.called
