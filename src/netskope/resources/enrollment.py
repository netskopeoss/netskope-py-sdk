"""Enrollment resource — manage Netskope Client enrollment token sets.

Token sets authenticate devices during initial registration with the
Netskope Client.  Routes come from the enrollment-service-configuration
gateway spec (``/api/v2/enrollment/tokenset``).

Example::

    for token_set in enrollment.list_token_sets():
        print(f"{token_set.id} created {token_set.created_date}")

    created = enrollment.create_token_set("Engineering Team", max_devices=100)
    enrollment.delete_token_set(created.id)
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.enrollment import EnrollmentTokenSet
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_TOKENSET_PATH = "/api/v2/enrollment/tokenset"

# Token type path segment: 0 for the authentication token, 1 for the
# encryption token (per the gateway spec's /tokenset/{id}/{type} route).
TOKEN_TYPE_AUTH = 0
TOKEN_TYPE_ENCRYPT = 1
_VALID_TOKEN_TYPES = (TOKEN_TYPE_AUTH, TOKEN_TYPE_ENCRYPT)
_VALID_ENFORCE_STATUSES = (0, 1)


def _build_list_params(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_create_payload(name: str, max_devices: int | None) -> dict[str, Any]:
    if not name:
        raise ValidationError("Token set name must be a non-empty string.")
    payload: dict[str, Any] = {"name": name}
    if max_devices is not None:
        payload["max_devices"] = max_devices
    return payload


def _build_update_payload(
    token_type: int | None,
    valid_until: int | None,
    enforce_status: int | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if token_type is not None:
        _validate_token_type(token_type)
        payload["type"] = token_type
    if valid_until is not None:
        payload["valid_until"] = valid_until
    if enforce_status is not None:
        if enforce_status not in _VALID_ENFORCE_STATUSES:
            raise ValidationError(
                f"Invalid enforce_status {enforce_status!r}. "
                "Must be 0 (Not Enforced) or 1 (Enforced)."
            )
        payload["enforce_status"] = enforce_status
    if not payload:
        raise ValidationError(
            "At least one of token_type, valid_until, or enforce_status is required."
        )
    return payload


def _validate_token_type(token_type: int) -> None:
    if token_type not in _VALID_TOKEN_TYPES:
        raise ValidationError(
            f"Invalid token_type {token_type!r}. Must be 0 (auth) or 1 (encrypt)."
        )


def _tokenset_path(token_id: int) -> str:
    return f"{_TOKENSET_PATH}/{validate_id(token_id, 'token_id')}"


def _parse_list(body: Any) -> builtins.list[EnrollmentTokenSet]:
    return [EnrollmentTokenSet.model_validate(item) for item in extract_list(body)]


class EnrollmentResource(SyncResource):
    """Synchronous interface to the Enrollment API."""

    def list_token_sets(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[EnrollmentTokenSet]:
        """List enrollment token sets.

        The API returns a bare JSON array of token sets (no pagination
        envelope).  ``limit`` and ``offset`` are passed through as query
        parameters when provided.

        Args:
            limit: Maximum number of token sets to return.
            offset: Number of records to skip.
        """
        body = self._get(_TOKENSET_PATH, **_build_list_params(limit, offset))
        return _parse_list(body)

    def create_token_set(
        self,
        name: str,
        *,
        max_devices: int | None = None,
    ) -> EnrollmentTokenSet:
        """Create an enrollment token set.

        Args:
            name: Display name for the token set.
            max_devices: Maximum number of devices that can enroll using
                this token set; ``None`` means unlimited.

        Raises:
            netskope.exceptions.ValidationError: If *name* is empty.
        """
        body = self._post(_TOKENSET_PATH, json=_build_create_payload(name, max_devices))
        return EnrollmentTokenSet.model_validate(extract_item(body))

    def update_token_set(
        self,
        token_id: int,
        *,
        token_type: int | None = None,
        valid_until: int | None = None,
        enforce_status: int | None = None,
    ) -> EnrollmentTokenSet:
        """Update an enrollment token set (gateway ``UpdateTokenSetDto``).

        Args:
            token_id: The token set identifier.
            token_type: Upsert a specific token — ``0`` (auth) or ``1``
                (encrypt).  Sent as the API's ``type`` key.
            valid_until: Token set validity in days.
            enforce_status: ``0`` (Not Enforced) or ``1`` (Enforced).

        Raises:
            netskope.exceptions.ValidationError: If no field is provided or
                a value is out of range.
        """
        payload = _build_update_payload(token_type, valid_until, enforce_status)
        body = self._patch(_tokenset_path(token_id), json=payload)
        return EnrollmentTokenSet.model_validate(extract_item(body))

    def delete_token_set(self, token_id: int) -> None:
        """Delete an enrollment token set.  Irreversible.

        Args:
            token_id: The token set identifier.
        """
        self._delete(_tokenset_path(token_id))

    def delete_token_type(self, token_id: int, token_type: int) -> EnrollmentTokenSet | None:
        """Delete one token (auth or encrypt) from a token set.

        Args:
            token_id: The token set identifier.
            token_type: ``0`` for the auth token, ``1`` for the encrypt token.

        Returns:
            The remaining token set, or ``None`` when both tokens are gone
            (the API answers 204 in that case).

        Raises:
            netskope.exceptions.ValidationError: If *token_type* is invalid.
        """
        _validate_token_type(token_type)
        body = self._delete(f"{_tokenset_path(token_id)}/{token_type}")
        if not body:
            return None
        return EnrollmentTokenSet.model_validate(extract_item(body))


class AsyncEnrollmentResource(AsyncResource):
    """Asynchronous interface to the Enrollment API."""

    async def list_token_sets(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[EnrollmentTokenSet]:
        """List enrollment token sets.

        See :meth:`EnrollmentResource.list_token_sets`.
        """
        body = await self._get(_TOKENSET_PATH, **_build_list_params(limit, offset))
        return _parse_list(body)

    async def create_token_set(
        self,
        name: str,
        *,
        max_devices: int | None = None,
    ) -> EnrollmentTokenSet:
        """Create an enrollment token set.

        See :meth:`EnrollmentResource.create_token_set`.
        """
        body = await self._post(_TOKENSET_PATH, json=_build_create_payload(name, max_devices))
        return EnrollmentTokenSet.model_validate(extract_item(body))

    async def update_token_set(
        self,
        token_id: int,
        *,
        token_type: int | None = None,
        valid_until: int | None = None,
        enforce_status: int | None = None,
    ) -> EnrollmentTokenSet:
        """Update an enrollment token set.

        See :meth:`EnrollmentResource.update_token_set`.
        """
        payload = _build_update_payload(token_type, valid_until, enforce_status)
        body = await self._patch(_tokenset_path(token_id), json=payload)
        return EnrollmentTokenSet.model_validate(extract_item(body))

    async def delete_token_set(self, token_id: int) -> None:
        """Delete an enrollment token set.  Irreversible."""
        await self._delete(_tokenset_path(token_id))

    async def delete_token_type(self, token_id: int, token_type: int) -> EnrollmentTokenSet | None:
        """Delete one token (auth or encrypt) from a token set.

        See :meth:`EnrollmentResource.delete_token_type`.
        """
        _validate_token_type(token_type)
        body = await self._delete(f"{_tokenset_path(token_id)}/{token_type}")
        if not body:
            return None
        return EnrollmentTokenSet.model_validate(extract_item(body))
