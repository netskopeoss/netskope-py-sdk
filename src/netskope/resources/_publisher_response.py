"""Publisher operations that retain the completed response for inspection."""

from __future__ import annotations

from typing import Any

from netskope.models._npa_requests import request_payload
from netskope.models.publishers import (
    Publisher,
    PublisherActionResult,
    PublisherAlertsConfiguration,
    PublisherAlertsConfigurationPatch,
    PublisherApp,
    PublisherRelease,
)
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id
from netskope.resources._npa_response import parse_item
from netskope.resources._response_list import parse_response_list
from netskope.resources.publishers import (
    _ALERTS_CONFIG_PATH,
    _BULK_PATH,
    _PATH,
    _RELEASES_PATH,
    _build_bulk_upgrade_payload,
    _build_create_payload,
    _build_page_params,
    _build_update_payload,
    _extract_publisher,
    _extract_token,
    _parse_publishers_page,
)
from netskope.response import ApiResponse


class PublisherResponses(SyncResource):
    """Explicit response access for synchronous publisher operations."""

    def get_alerts_configuration(self) -> ApiResponse[PublisherAlertsConfiguration]:
        response = self._transport.request("GET", _ALERTS_CONFIG_PATH)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PublisherAlertsConfiguration)
        )

    def update_alerts_configuration_request(
        self,
        request: PublisherAlertsConfigurationPatch,
    ) -> ApiResponse[PublisherAlertsConfiguration]:
        payload = request_payload(request, PublisherAlertsConfigurationPatch)
        response = self._transport.request("PUT", _ALERTS_CONFIG_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PublisherAlertsConfiguration)
        )

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> ApiResponse[Page[Publisher]]:
        params = _build_page_params(filter_expr, fields, offset, limit)
        response = self._transport.request("GET", _PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: _parse_publishers_page(raw.json(), 0 if offset is None else offset, limit),
        )

    def get(self, publisher_id: int) -> ApiResponse[Publisher]:
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}"
        response = self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    def create(
        self,
        name: str,
        *,
        lbroker_connect: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[Publisher]:
        payload = _build_create_payload(name, lbroker_connect, extra_fields)
        response = self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[Publisher]:
        payload = _build_update_payload(name, extra_fields)
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}"
        response = self._transport.request("PATCH", path, json=payload)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    def list_apps(self, publisher_id: int) -> ApiResponse[list[PublisherApp]]:
        """List a publisher's associated applications as typed records."""
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}/apps"
        response = self._transport.request("GET", path)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PublisherApp, "apps")
        )

    def list_releases(self) -> ApiResponse[list[PublisherRelease]]:
        """List available publisher releases and retain the response envelope."""
        response = self._transport.request("GET", _RELEASES_PATH)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PublisherRelease, "releases")
        )

    def create_registration_token(self, publisher_id: int) -> ApiResponse[str]:
        """Create a registration token, available through typed parsing or original JSON."""
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}/registration_token"
        response = self._transport.request("POST", path)
        return ApiResponse(response, lambda raw: _extract_token(raw.json()))

    def bulk_upgrade(self, publisher_ids: list[int]) -> ApiResponse[PublisherActionResult]:
        """Request an upgrade and parse its acknowledgment."""
        payload = _build_bulk_upgrade_payload(publisher_ids)
        response = self._transport.request("PUT", _BULK_PATH, json=payload)
        return ApiResponse(response, lambda raw: PublisherActionResult.model_validate(raw.json()))


class AsyncPublisherResponses(AsyncResource):
    """Explicit response access for asynchronous publisher operations."""

    async def get_alerts_configuration(self) -> ApiResponse[PublisherAlertsConfiguration]:
        response = await self._transport.request("GET", _ALERTS_CONFIG_PATH)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PublisherAlertsConfiguration)
        )

    async def update_alerts_configuration_request(
        self,
        request: PublisherAlertsConfigurationPatch,
    ) -> ApiResponse[PublisherAlertsConfiguration]:
        payload = request_payload(request, PublisherAlertsConfigurationPatch)
        response = await self._transport.request("PUT", _ALERTS_CONFIG_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PublisherAlertsConfiguration)
        )

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> ApiResponse[Page[Publisher]]:
        params = _build_page_params(filter_expr, fields, offset, limit)
        response = await self._transport.request("GET", _PATH, params=params or None)
        return ApiResponse(
            response,
            lambda raw: _parse_publishers_page(raw.json(), 0 if offset is None else offset, limit),
        )

    async def get(self, publisher_id: int) -> ApiResponse[Publisher]:
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}"
        response = await self._transport.request("GET", path)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    async def create(
        self,
        name: str,
        *,
        lbroker_connect: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[Publisher]:
        payload = _build_create_payload(name, lbroker_connect, extra_fields)
        response = await self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    async def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> ApiResponse[Publisher]:
        payload = _build_update_payload(name, extra_fields)
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}"
        response = await self._transport.request("PATCH", path, json=payload)
        return ApiResponse(response, lambda raw: _extract_publisher(raw.json()))

    async def list_apps(self, publisher_id: int) -> ApiResponse[list[PublisherApp]]:
        """List a publisher's associated applications as typed records."""
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}/apps"
        response = await self._transport.request("GET", path)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PublisherApp, "apps")
        )

    async def list_releases(self) -> ApiResponse[list[PublisherRelease]]:
        """List available publisher releases and retain the response envelope."""
        response = await self._transport.request("GET", _RELEASES_PATH)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PublisherRelease, "releases")
        )

    async def create_registration_token(self, publisher_id: int) -> ApiResponse[str]:
        """Create a registration token and retain its original response."""
        path = f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}/registration_token"
        response = await self._transport.request("POST", path)
        return ApiResponse(response, lambda raw: _extract_token(raw.json()))

    async def bulk_upgrade(self, publisher_ids: list[int]) -> ApiResponse[PublisherActionResult]:
        """Request an upgrade and parse its acknowledgment."""
        payload = _build_bulk_upgrade_payload(publisher_ids)
        response = await self._transport.request("PUT", _BULK_PATH, json=payload)
        return ApiResponse(response, lambda raw: PublisherActionResult.model_validate(raw.json()))
