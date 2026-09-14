"""One-page device inventory and typed supported-OS responses."""

from __future__ import annotations

from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.devices import Device, SupportedOperatingSystems
from netskope.resources.shared.admin import item, page, page_params
from netskope.response import ApiResponse


class DevicesResponses(SyncResource):
    def list_page(self, *, limit: int = 25, offset: int = 0) -> ApiResponse[Page[Device]]:
        params = page_params(limit, offset)
        response = self._transport.request("GET", "/api/v2/steering/devices", params=params)
        return ApiResponse(
            response, lambda raw: page(raw, Device, "devices", limit=limit, offset=offset)
        )

    def supported_os(self) -> ApiResponse[SupportedOperatingSystems]:
        response = self._transport.request("GET", "/api/v2/devices/supportedos")
        return ApiResponse(response, lambda raw: item(raw, SupportedOperatingSystems))


class AsyncDevicesResponses(AsyncResource):
    async def list_page(self, *, limit: int = 25, offset: int = 0) -> ApiResponse[Page[Device]]:
        params = page_params(limit, offset)
        response = await self._transport.request("GET", "/api/v2/steering/devices", params=params)
        return ApiResponse(
            response, lambda raw: page(raw, Device, "devices", limit=limit, offset=offset)
        )

    async def supported_os(self) -> ApiResponse[SupportedOperatingSystems]:
        response = await self._transport.request("GET", "/api/v2/devices/supportedos")
        return ApiResponse(response, lambda raw: item(raw, SupportedOperatingSystems))
