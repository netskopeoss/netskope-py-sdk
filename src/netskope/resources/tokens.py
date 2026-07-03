"""API Tokens resource — create, inspect, update, reissue, and revoke API tokens.

Backed by the API Token Management API at ``/api/v2/auth/tokens``.

Example::

    for token in tokens.list():
        print(f"{token.id}: {token.name} (expires {token.expires})")

    created = tokens.create(
        "ci-token",
        ["/api/v2/events"],  # bare strings default to read-only ("r")
        expires=datetime(2027, 1, 1, tzinfo=UTC),
    )
    secret = created.token  # returned exactly once — store securely

.. warning::
    The token secret is present only in the response to :meth:`create` (and
    :meth:`reissue`).  It cannot be retrieved again — store it securely and
    never log it.
"""

from __future__ import annotations

import builtins
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.tokens import ApiToken, ApiTokenEndpoint
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_TOKENS_PATH = "/api/v2/auth/tokens"

_VALID_PERMISSIONS = ("r", "rw")

# Accepted shapes for an endpoint scope: a typed model, a spec-shaped mapping
# ({"endpoint": ..., "permissions": "r"|"rw"}), or a bare endpoint string
# (defaults to read-only, following least privilege).
EndpointInput = ApiTokenEndpoint | Mapping[str, Any] | str


def _token_path(token_id: str | int) -> str:
    return f"{_TOKENS_PATH}/{validate_id(token_id, 'token_id')}"


def _to_epoch_seconds(value: datetime | int) -> int:
    return int(value.timestamp()) if isinstance(value, datetime) else value


def _normalize_endpoint(item: EndpointInput) -> dict[str, str]:
    if isinstance(item, ApiTokenEndpoint):
        endpoint, permissions = item.endpoint, item.permissions
    elif isinstance(item, str):
        endpoint, permissions = item, "r"
    elif isinstance(item, Mapping):
        endpoint = str(item.get("endpoint") or "")
        permissions = str(item.get("permissions") or "r")
    else:
        raise ValidationError(
            f"Invalid endpoint scope {item!r}. Expected an ApiTokenEndpoint, "
            'a {"endpoint": ..., "permissions": ...} mapping, or a string.'
        )
    if not endpoint:
        raise ValidationError(f"Endpoint scope {item!r} has an empty 'endpoint' value.")
    if permissions not in _VALID_PERMISSIONS:
        raise ValidationError(
            f"Invalid permissions {permissions!r} for endpoint {endpoint!r}. "
            f"Must be one of: {', '.join(_VALID_PERMISSIONS)}"
        )
    return {"endpoint": endpoint, "permissions": permissions}


def _normalize_endpoints(endpoints: Sequence[EndpointInput]) -> builtins.list[dict[str, str]]:
    if not endpoints:
        raise ValidationError("At least one endpoint scope is required.")
    return [_normalize_endpoint(item) for item in endpoints]


def _build_create_payload(
    name: str,
    endpoints: Sequence[EndpointInput],
    expires: datetime | int,
) -> dict[str, Any]:
    return {
        "name": name,
        "expires": _to_epoch_seconds(expires),
        "endpoints": _normalize_endpoints(endpoints),
    }


def _build_update_payload(
    name: str | None,
    expires: datetime | int | None,
    endpoints: Sequence[EndpointInput] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if expires is not None:
        payload["expires"] = _to_epoch_seconds(expires)
    if endpoints is not None:
        payload["endpoints"] = _normalize_endpoints(endpoints)
    if not payload:
        raise ValidationError("Nothing to update. Provide name, expires, and/or endpoints.")
    return payload


def _build_list_params(fields: builtins.list[str] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if fields:
        params["fields"] = ",".join(fields)
    return params


class TokensResource(SyncResource):
    """Synchronous interface to the API Token Management API."""

    def list(self, *, fields: builtins.list[str] | None = None) -> builtins.list[ApiToken]:
        """List all API tokens in the tenant.

        Token secrets are never included — :attr:`ApiToken.token` is ``None``.

        Args:
            fields: Optional projection of fields to return
                (e.g. ``["id", "name", "expires", "endpoints"]``).
        """
        body = self._get(_TOKENS_PATH, **_build_list_params(fields))
        return [ApiToken.model_validate(item) for item in extract_list(body)]

    def get(self, token_id: str | int) -> ApiToken:
        """Get metadata for a single API token.  The secret is never returned.

        Args:
            token_id: The token identifier (a string per the API spec;
                integers are accepted and stringified).
        """
        body = self._get(_token_path(token_id))
        return ApiToken.model_validate(extract_item(body))

    def create(
        self,
        name: str,
        endpoints: Sequence[EndpointInput],
        *,
        expires: datetime | int,
    ) -> ApiToken:
        """Create a new API token.

        .. warning::
            The returned :attr:`ApiToken.token` secret is provided exactly
            once and cannot be retrieved again — store it securely and never
            log it.

        Args:
            name: Descriptive, tenant-unique token name.
            endpoints: Endpoint scopes to grant.  Each item is an
                :class:`~netskope.models.tokens.ApiTokenEndpoint`, a mapping
                like ``{"endpoint": "/api/v2/events", "permissions": "rw"}``,
                or a bare endpoint string (defaults to read-only ``"r"``).
            expires: Expiry as a :class:`~datetime.datetime` or seconds since
                the Unix epoch.  Required by the API.

        Raises:
            netskope.exceptions.ValidationError: If *endpoints* is empty or an
                endpoint scope is malformed.
        """
        body = self._post(_TOKENS_PATH, json=_build_create_payload(name, endpoints, expires))
        return ApiToken.model_validate(extract_item(body))

    def update(
        self,
        token_id: str | int,
        *,
        name: str | None = None,
        expires: datetime | int | None = None,
        endpoints: Sequence[EndpointInput] | None = None,
    ) -> ApiToken:
        """Update a token's name, expiry, and/or endpoint scopes (PATCH).

        The endpoint list is a full replacement, not additive.  The API
        expects all of ``name``, ``expires``, and ``endpoints`` on a plain
        update; omitted fields are left out of the request and the server
        may reject a partial body.  The token secret is unchanged — use
        :meth:`reissue` to rotate it.

        Args:
            token_id: The token identifier.
            name: New token name.
            expires: New expiry (:class:`~datetime.datetime` or epoch seconds).
            endpoints: Replacement endpoint scopes (see :meth:`create`).

        Raises:
            netskope.exceptions.ValidationError: If no fields are provided.
        """
        payload = _build_update_payload(name, expires, endpoints)
        body = self._patch(_token_path(token_id), json=payload)
        return ApiToken.model_validate(extract_item(body))

    def reissue(self, token_id: str | int) -> ApiToken:
        """Reissue (rotate) a token's secret, invalidating the old one.

        .. warning::
            The new :attr:`ApiToken.token` secret is returned exactly once —
            store it securely and never log it.

        Args:
            token_id: The token identifier.
        """
        body = self._patch(_token_path(token_id), json={"operation": "reissue"})
        return ApiToken.model_validate(extract_item(body))

    def delete(self, token_id: str | int) -> None:
        """Revoke (delete) an API token permanently.  Irreversible.

        Any integration using the token immediately loses access.

        Args:
            token_id: The token identifier.
        """
        self._delete(_token_path(token_id))

    # The Netskope console and CLI call deletion "revoke".
    revoke = delete


class AsyncTokensResource(AsyncResource):
    """Asynchronous interface to the API Token Management API."""

    async def list(self, *, fields: builtins.list[str] | None = None) -> builtins.list[ApiToken]:
        """List all API tokens.  See :meth:`TokensResource.list`."""
        body = await self._get(_TOKENS_PATH, **_build_list_params(fields))
        return [ApiToken.model_validate(item) for item in extract_list(body)]

    async def get(self, token_id: str | int) -> ApiToken:
        """Get metadata for a single API token.  See :meth:`TokensResource.get`."""
        body = await self._get(_token_path(token_id))
        return ApiToken.model_validate(extract_item(body))

    async def create(
        self,
        name: str,
        endpoints: Sequence[EndpointInput],
        *,
        expires: datetime | int,
    ) -> ApiToken:
        """Create a new API token.  See :meth:`TokensResource.create`.

        .. warning::
            The returned secret is provided exactly once — store it securely.
        """
        body = await self._post(_TOKENS_PATH, json=_build_create_payload(name, endpoints, expires))
        return ApiToken.model_validate(extract_item(body))

    async def update(
        self,
        token_id: str | int,
        *,
        name: str | None = None,
        expires: datetime | int | None = None,
        endpoints: Sequence[EndpointInput] | None = None,
    ) -> ApiToken:
        """Update a token's metadata (PATCH).  See :meth:`TokensResource.update`."""
        payload = _build_update_payload(name, expires, endpoints)
        body = await self._patch(_token_path(token_id), json=payload)
        return ApiToken.model_validate(extract_item(body))

    async def reissue(self, token_id: str | int) -> ApiToken:
        """Rotate a token's secret.  See :meth:`TokensResource.reissue`."""
        body = await self._patch(_token_path(token_id), json={"operation": "reissue"})
        return ApiToken.model_validate(extract_item(body))

    async def delete(self, token_id: str | int) -> None:
        """Revoke (delete) an API token permanently.  Irreversible."""
        await self._delete(_token_path(token_id))

    # The Netskope console and CLI call deletion "revoke".
    revoke = delete
