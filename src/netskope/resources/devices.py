"""Devices resource — device inventory, supported OS lookup, and device tags.

Example::

    # Device inventory (not routed on every tenant — see ``list``)
    for device in client.devices.list():
        print(device.host_name)

    # Operating systems the Netskope Client supports
    info = client.devices.supported_os()

    # Device tags (device classification system)
    tags = client.devices.tags.list()
    tag = client.devices.tags.create("Production Servers")
"""

from __future__ import annotations

import builtins
import functools
import re
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.devices import Device, DeviceTag
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

_DEVICES_PATH = "/api/v2/steering/devices"
_SUPPORTED_OS_PATH = "/api/v2/devices/supportedos"

# The device-tag service is specced in the API gateway as endpoints/devices/
# tag.yaml with path ``/device/tags``; the gateway mounts specs at
# ``/api/v2/{service-directory}{path}``, so the public route is
# ``/api/v2/devices/device/tags`` (not ``/api/v2/devices/tags``).
_TAGS_PATH = "/api/v2/devices/device/tags"
_TAGS_QUERY_PATH = f"{_TAGS_PATH}/gettags"

# Tag names and descriptions accept alphanumerics, hyphens, and spaces only
# (``CreateTagDto`` / ``UpdateTagDto`` pattern in the gateway spec).  Validate
# client-side so callers fail fast with a clear message.
_TAG_TEXT_RE = re.compile(r"^[0-9a-zA-Z\-\s]+$")

# gettags paging bounds per the gateway spec (default limit 20, max 100).
_TAGS_DEFAULT_LIMIT = 20
_TAGS_MAX_LIMIT = 100


def _extract_devices(body: dict[str, Any]) -> builtins.list[dict[str, Any]]:
    return extract_list(body, "devices")


def _extract_tags(body: dict[str, Any]) -> builtins.list[dict[str, Any]]:
    # Envelope: {"success": true, "data": {"data": [...], "total_count": N}}
    return extract_list(body, "data")


def _coerce_tag_id(tag_id: int | str) -> int:
    """Validate *tag_id* and return it as an ``int`` (tag IDs are numeric)."""
    validated = validate_id(tag_id, "tag_id")
    if not validated.isdigit():
        raise ValidationError(f"Invalid tag_id: {tag_id!r} (device tag IDs are numeric)")
    return int(validated)


def _validate_tag_text(value: str, name: str) -> str:
    if not _TAG_TEXT_RE.match(value):
        raise ValidationError(
            f"Invalid {name}: {value!r} "
            "(only alphanumeric characters, hyphens, and spaces are allowed)"
        )
    return value


def _build_tags_query(name: str | None, offset: int, limit: int) -> dict[str, Any]:
    if not 1 <= limit <= _TAGS_MAX_LIMIT:
        raise ValidationError(f"Invalid limit {limit!r}. Must be between 1 and {_TAGS_MAX_LIMIT}.")
    if offset < 0:
        raise ValidationError(f"Invalid offset {offset!r}. Must be >= 0.")
    payload: dict[str, Any] = {"offset": offset, "limit": limit}
    if name is not None:
        payload["name"] = name
    return payload


def _build_create_payload(name: str, description: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": _validate_tag_text(name, "name")}
    if description is not None:
        payload["description"] = _validate_tag_text(description, "description")
    return payload


def _build_update_payload(name: str | None, description: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = _validate_tag_text(name, "name")
    if description is not None:
        payload["description"] = _validate_tag_text(description, "description")
    if not payload:
        raise ValidationError("Nothing to update. Provide name and/or description.")
    return payload


def _tag_from_query_response(body: dict[str, Any], tag_id: int) -> DeviceTag:
    items = _extract_tags(body)
    if not items:
        raise NotFoundError(f"Device tag {tag_id} not found", status_code=404, body=body)
    return DeviceTag.model_validate(items[0])


class DeviceTagsResource(SyncResource):
    """Synchronous interface to device tags (``/api/v2/devices/device/tags``)."""

    def list(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> builtins.list[DeviceTag]:
        """List device tags (one page per call).

        Queries ``POST /api/v2/devices/device/tags/gettags`` — the tag API
        pages via the request *body* (``offset``/``limit``), so this returns
        a single page rather than a lazy paginator.

        Args:
            name: Case-insensitive tag-name filter.
            offset: Number of tags to skip (0-based).
            limit: Page size (1-100, default 20).

        Raises:
            netskope.exceptions.ValidationError: If *offset* or *limit* is
                out of range.
        """
        body = self._post(_TAGS_QUERY_PATH, json=_build_tags_query(name, offset, limit))
        return [DeviceTag.model_validate(item) for item in _extract_tags(body)]

    def get(self, tag_id: int | str) -> DeviceTag:
        """Get a device tag by its numeric ID.

        The tag API has no ``GET /tags/{id}`` route; lookup is done via
        ``POST .../gettags`` with an ``id`` filter.

        Raises:
            netskope.exceptions.ValidationError: If *tag_id* is not numeric.
            netskope.exceptions.NotFoundError: If the tag does not exist.
        """
        coerced = _coerce_tag_id(tag_id)
        body = self._post(_TAGS_QUERY_PATH, json={"id": coerced})
        return _tag_from_query_response(body, coerced)

    def create(self, name: str, *, description: str | None = None) -> DeviceTag:
        """Create a device tag.

        Sends ``POST /api/v2/devices/device/tags``.  Tag names must be unique
        within the tenant (the API returns 409 on conflict).

        Args:
            name: Tag name (alphanumerics, hyphens, and spaces only).
            description: Optional description (same character restrictions).

        Raises:
            netskope.exceptions.ValidationError: If *name* or *description*
                contains disallowed characters.
        """
        body = self._post(_TAGS_PATH, json=_build_create_payload(name, description))
        return DeviceTag.model_validate(extract_item(body))

    def update(
        self,
        tag_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> DeviceTag:
        """Update a device tag's name and/or description.

        Sends ``PATCH /api/v2/devices/device/tags/{id}`` (the gateway spec
        uses PATCH, not PUT) with only the provided fields.

        Raises:
            netskope.exceptions.ValidationError: If neither *name* nor
                *description* is provided, or a value contains disallowed
                characters.
        """
        coerced = _coerce_tag_id(tag_id)
        body = self._patch(f"{_TAGS_PATH}/{coerced}", json=_build_update_payload(name, description))
        return DeviceTag.model_validate(extract_item(body))

    def delete(self, tag_id: int | str) -> None:
        """Delete a device tag by ID.  Irreversible.

        The API refuses (HTTP 400) to delete a tag that is still associated
        with devices or device classifications.
        """
        self._delete(f"{_TAGS_PATH}/{_coerce_tag_id(tag_id)}")


class DevicesResource(SyncResource):
    """Synchronous interface to the Devices API."""

    def list(self, *, page_size: int = 100) -> SyncPaginatedResponse[Device]:
        """List managed devices enrolled in the tenant.

        Queries ``GET /api/v2/steering/devices`` with ``limit``/``offset``
        pagination.

        .. note::
            The API gateway specs contain **no** device-inventory route —
            neither under ``steering/`` nor ``devices/`` — so this legacy
            path is not routed on every tenant and commonly returns
            HTTP 404 ("no Route matched").  Catch
            :class:`~netskope.exceptions.NotFoundError` if your tenant may
            not expose it; the ``events`` client-status data is an
            alternative source of endpoint inventory.

        Args:
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DEVICES_PATH,
            params={},
            model=Device,
            page_size=page_size,
            extract=_extract_devices,
        )

    def supported_os(self) -> builtins.list[dict[str, Any]] | dict[str, Any]:
        """List operating systems supported by the Netskope Client.

        Queries ``GET /api/v2/devices/supportedos``.  Per the gateway spec
        the response is ``{"available_os": ["windows", "mac", ...]}``; it is
        returned unmodified.
        """
        return self._get(_SUPPORTED_OS_PATH)

    @functools.cached_property
    def tags(self) -> DeviceTagsResource:
        """Access the device tags API."""
        return DeviceTagsResource(self._transport)


class AsyncDeviceTagsResource(AsyncResource):
    """Asynchronous interface to device tags."""

    async def list(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> builtins.list[DeviceTag]:
        """List device tags (one page per call).

        See :meth:`DeviceTagsResource.list`.
        """
        body = await self._post(_TAGS_QUERY_PATH, json=_build_tags_query(name, offset, limit))
        return [DeviceTag.model_validate(item) for item in _extract_tags(body)]

    async def get(self, tag_id: int | str) -> DeviceTag:
        """Get a device tag by its numeric ID.

        See :meth:`DeviceTagsResource.get`.
        """
        coerced = _coerce_tag_id(tag_id)
        body = await self._post(_TAGS_QUERY_PATH, json={"id": coerced})
        return _tag_from_query_response(body, coerced)

    async def create(self, name: str, *, description: str | None = None) -> DeviceTag:
        """Create a device tag.  See :meth:`DeviceTagsResource.create`."""
        body = await self._post(_TAGS_PATH, json=_build_create_payload(name, description))
        return DeviceTag.model_validate(extract_item(body))

    async def update(
        self,
        tag_id: int | str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> DeviceTag:
        """Update a device tag's name and/or description.

        See :meth:`DeviceTagsResource.update`.
        """
        coerced = _coerce_tag_id(tag_id)
        body = await self._patch(
            f"{_TAGS_PATH}/{coerced}", json=_build_update_payload(name, description)
        )
        return DeviceTag.model_validate(extract_item(body))

    async def delete(self, tag_id: int | str) -> None:
        """Delete a device tag by ID.  Irreversible."""
        await self._delete(f"{_TAGS_PATH}/{_coerce_tag_id(tag_id)}")


class AsyncDevicesResource(AsyncResource):
    """Asynchronous interface to the Devices API."""

    def list(self, *, page_size: int = 100) -> AsyncPaginatedResponse[Device]:
        """List managed devices enrolled in the tenant.

        See :meth:`DevicesResource.list` — this legacy route is not exposed
        on every tenant and may return HTTP 404.
        """
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_DEVICES_PATH,
            params={},
            model=Device,
            page_size=page_size,
            extract=_extract_devices,
        )

    async def supported_os(self) -> builtins.list[dict[str, Any]] | dict[str, Any]:
        """List operating systems supported by the Netskope Client.

        See :meth:`DevicesResource.supported_os`.
        """
        return await self._get(_SUPPORTED_OS_PATH)

    @functools.cached_property
    def tags(self) -> AsyncDeviceTagsResource:
        """Access the device tags API."""
        return AsyncDeviceTagsResource(self._transport)
