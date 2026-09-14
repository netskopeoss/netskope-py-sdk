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
from collections.abc import AsyncIterator, Iterator
from typing import Any

from netskope.core.ids import extract_list
from netskope.core.pagination import AsyncPaginatedResponse, Page, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.devices import Device, DeviceTag
from netskope.resources.devices.decoder import AsyncDevicesResponses, DevicesResponses
from netskope.resources.devices.paths import (
    _TAGS_DEFAULT_LIMIT,
    _TAGS_MAX_LIMIT,
    _TAGS_PATH,
    _coerce_tag_id,
)
from netskope.resources.devices.tags_decoder import AsyncDeviceTagResponses, DeviceTagResponses

_DEVICES_PATH = "/api/v2/steering/devices"
_SUPPORTED_OS_PATH = "/api/v2/devices/supportedos"

# The device-tag service is specced in the API gateway as endpoints/devices/
# tag.yaml with path ``/device/tags``; the gateway mounts specs at
# ``/api/v2/{service-directory}{path}``, so the public route is
# ``/api/v2/devices/device/tags`` (not ``/api/v2/devices/tags``).

# gettags paging bounds per the gateway spec (default limit 20, max 100).
#
# tag.yaml is internally inconsistent about the ceiling: TagQueryDto (:933-937)
# declares ``minimum: 1, maximum: 100`` with no special case, while the prose at
# :125 says "limit - Maximum items to retrieve (default: 20, max: 100, query
# with count's max: 10)". The counts-bearing queries are exactly the ones the
# traversal here issues — empty body and name filter (:109-116, :131). Schema
# validation accepts 100 either way, so the page-size default follows the
# schema; lower it to 10 if a tenant rejects larger counts-bearing pages.


def _extract_devices(body: dict[str, Any]) -> builtins.list[dict[str, Any]]:
    return extract_list(body, "devices")


class DeviceTagsResource(SyncResource):
    """Synchronous interface to device tags (``/api/v2/devices/device/tags``)."""

    @functools.cached_property
    def with_response(self) -> DeviceTagResponses:
        """Inspect the completed HTTP response alongside each typed read."""

        return DeviceTagResponses(self._transport)

    def list_page(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> Page[DeviceTag]:
        """Fetch one POST-body page with its verified ``total_count`` metadata."""
        return self.with_response.list_page(name=name, offset=offset, limit=limit).parse()

    def iter_pages(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> Iterator[Page[DeviceTag]]:
        """Traverse tags using returned-record offsets, with incomplete scans raising.

        A known total determines completion. Without a total, an empty page is
        required because the server can return fewer records than requested.
        This does not provide a snapshot of tags changing during iteration.
        """
        for response in self.with_response.iter_pages(
            name=name, offset=offset, page_size=page_size, max_pages=max_pages
        ):
            yield response.parse()

    def iter_all(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> Iterator[DeviceTag]:
        """Yield every tag; see :meth:`iter_pages` for traversal guarantees."""
        for page in self.iter_pages(
            name=name, offset=offset, page_size=page_size, max_pages=max_pages
        ):
            yield from page.items

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
        return self.list_page(name=name, offset=offset, limit=limit).items

    def get(self, tag_id: int | str) -> DeviceTag:
        """Get a device tag by its numeric ID.

        The tag API has no ``GET /tags/{id}`` route; lookup is done via
        ``POST .../gettags`` with an ``id`` filter.

        Raises:
            netskope.exceptions.ValidationError: If *tag_id* is not numeric.
            netskope.exceptions.NotFoundError: If the tag does not exist.
        """
        return self.with_response.get(tag_id).parse()

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
        return self.with_response.create(name, description=description).parse()

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
        return self.with_response.update(tag_id, name=name, description=description).parse()

    def delete(self, tag_id: int | str) -> None:
        """Delete a device tag by ID.  Irreversible.

        The API refuses (HTTP 400) to delete a tag that is still associated
        with devices or device classifications.
        """
        self._delete(f"{_TAGS_PATH}/{_coerce_tag_id(tag_id)}")


class DevicesResource(SyncResource):
    """Synchronous interface to the Devices API."""

    @functools.cached_property
    def with_response(self) -> DevicesResponses:
        return DevicesResponses(self._transport)

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

    @functools.cached_property
    def with_response(self) -> AsyncDeviceTagResponses:
        """Inspect the completed HTTP response alongside each typed read."""

        return AsyncDeviceTagResponses(self._transport)

    async def list_page(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        limit: int = _TAGS_DEFAULT_LIMIT,
    ) -> Page[DeviceTag]:
        """Fetch one tag page. See :meth:`DeviceTagsResource.list_page`."""
        return (await self.with_response.list_page(name=name, offset=offset, limit=limit)).parse()

    async def iter_pages(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> AsyncIterator[Page[DeviceTag]]:
        """Traverse tags. See :meth:`DeviceTagsResource.iter_pages`."""
        async for response in self.with_response.iter_pages(
            name=name, offset=offset, page_size=page_size, max_pages=max_pages
        ):
            yield response.parse()

    async def iter_all(
        self,
        *,
        name: str | None = None,
        offset: int = 0,
        page_size: int = _TAGS_MAX_LIMIT,
        max_pages: int = 1_000,
    ) -> AsyncIterator[DeviceTag]:
        """Yield every tag. See :meth:`DeviceTagsResource.iter_all`."""
        async for page in self.iter_pages(
            name=name, offset=offset, page_size=page_size, max_pages=max_pages
        ):
            for item in page.items:
                yield item

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
        return (await self.list_page(name=name, offset=offset, limit=limit)).items

    async def get(self, tag_id: int | str) -> DeviceTag:
        """Get a device tag by its numeric ID.

        See :meth:`DeviceTagsResource.get`.
        """
        return (await self.with_response.get(tag_id)).parse()

    async def create(self, name: str, *, description: str | None = None) -> DeviceTag:
        """Create a device tag.  See :meth:`DeviceTagsResource.create`."""
        return (await self.with_response.create(name, description=description)).parse()

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
        return (await self.with_response.update(tag_id, name=name, description=description)).parse()

    async def delete(self, tag_id: int | str) -> None:
        """Delete a device tag by ID.  Irreversible."""
        await self._delete(f"{_TAGS_PATH}/{_coerce_tag_id(tag_id)}")


class AsyncDevicesResource(AsyncResource):
    """Asynchronous interface to the Devices API."""

    @functools.cached_property
    def with_response(self) -> AsyncDevicesResponses:
        return AsyncDevicesResponses(self._transport)

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
