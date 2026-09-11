"""Typed private-app responses, preserving legacy iterator and dictionary APIs."""

from __future__ import annotations

from netskope.models._npa_requests import request_payload
from netskope.models.private_apps import (
    PrivateApp,
    PrivateAppCreate,
    PrivateAppDiscoveryRequest,
    PrivateAppDiscoverySettings,
    PrivateAppMutationResult,
    PrivateAppPatch,
    PrivateAppPolicyUsage,
    PrivateAppTag,
)
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import id_strings, validate_id
from netskope.resources._npa_response import page_params, parse_item, parse_page
from netskope.resources._response_list import parse_response_list
from netskope.resources.private_apps import (
    _DISCOVERY_PATH,
    _PATH,
    _POLICY_IN_USE_PATH,
    _PUBLISHERS_PATH,
    _TAGS_PATH,
    _TAGS_POLICY_IN_USE_PATH,
    _build_list_params,
    _publisher_assoc_payload,
    _tag_bulk_payload,
    _tag_create_payload,
)
from netskope.response import ApiResponse


class PrivateAppResponses(SyncResource):
    """Same-request private-app results with explicit typed decoding."""

    def bulk_delete(self, app_ids: list[int]) -> ApiResponse[PrivateAppMutationResult | None]:
        payload = {"private_app_ids": id_strings(app_ids, "app_ids")}
        response = self._transport.request("DELETE", _PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: (
                PrivateAppMutationResult.model_validate(raw.json()) if raw.content else None
            ),
        )

    def remove_publishers(
        self,
        app_ids: list[int],
        publisher_ids: list[int],
    ) -> ApiResponse[PrivateAppMutationResult | None]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = self._transport.request("DELETE", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: (
                PrivateAppMutationResult.model_validate(raw.json()) if raw.content else None
            ),
        )

    def list_page(
        self,
        *,
        query: str | None = None,
        app_name: str | None = None,
        publisher_name: str | None = None,
        reachable: bool | None = None,
        clientless_access: bool | None = None,
        host: str | None = None,
        in_policy: bool | None = None,
        protocol: str | None = None,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[PrivateApp]]:
        params = {
            **_build_list_params(
                query,
                app_name,
                publisher_name,
                reachable,
                clientless_access,
                host,
                in_policy,
                protocol,
                filter_expr,
                fields,
            ),
            **page_params(limit, offset),
        }
        response = self._transport.request("GET", _PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), PrivateApp, limit, offset, "private_apps")
        )

    def get(self, app_id: int | str) -> ApiResponse[PrivateApp]:
        response = self._transport.request("GET", f"{_PATH}/{validate_id(app_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    def create_request(self, request: PrivateAppCreate) -> ApiResponse[PrivateApp]:
        payload = request_payload(request, PrivateAppCreate)
        response = self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    def update_request(
        self, app_id: int | str, request: PrivateAppPatch
    ) -> ApiResponse[PrivateApp]:
        payload = request_payload(request, PrivateAppPatch)
        response = self._transport.request("PATCH", f"{_PATH}/{validate_id(app_id)}", json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    def get_policy_in_use(self, app_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        response = self._transport.request(
            "POST",
            _POLICY_IN_USE_PATH,
            json={"ids": id_strings(app_ids, "app_ids")},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: PrivateAppPolicyUsage.model_validate(raw.json()))

    def get_discovery_settings(self) -> ApiResponse[PrivateAppDiscoverySettings]:
        response = self._transport.request("GET", _DISCOVERY_PATH)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PrivateAppDiscoverySettings)
        )

    def update_discovery_settings(
        self, request: PrivateAppDiscoveryRequest
    ) -> ApiResponse[PrivateAppDiscoverySettings]:
        payload = request_payload(request, PrivateAppDiscoveryRequest)
        response = self._transport.request("POST", _DISCOVERY_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PrivateAppDiscoverySettings)
        )

    def add_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = self._transport.request("PATCH", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    def replace_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = self._transport.request("PUT", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )


class AsyncPrivateAppResponses(AsyncResource):
    """Same-request private-app results with explicit typed decoding."""

    async def bulk_delete(self, app_ids: list[int]) -> ApiResponse[PrivateAppMutationResult | None]:
        payload = {"private_app_ids": id_strings(app_ids, "app_ids")}
        response = await self._transport.request("DELETE", _PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: (
                PrivateAppMutationResult.model_validate(raw.json()) if raw.content else None
            ),
        )

    async def remove_publishers(
        self,
        app_ids: list[int],
        publisher_ids: list[int],
    ) -> ApiResponse[PrivateAppMutationResult | None]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = await self._transport.request("DELETE", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: (
                PrivateAppMutationResult.model_validate(raw.json()) if raw.content else None
            ),
        )

    async def list_page(
        self,
        *,
        query: str | None = None,
        app_name: str | None = None,
        publisher_name: str | None = None,
        reachable: bool | None = None,
        clientless_access: bool | None = None,
        host: str | None = None,
        in_policy: bool | None = None,
        protocol: str | None = None,
        filter_expr: str | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[PrivateApp]]:
        params = {
            **_build_list_params(
                query,
                app_name,
                publisher_name,
                reachable,
                clientless_access,
                host,
                in_policy,
                protocol,
                filter_expr,
                fields,
            ),
            **page_params(limit, offset),
        }
        response = await self._transport.request("GET", _PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), PrivateApp, limit, offset, "private_apps")
        )

    async def get(self, app_id: int | str) -> ApiResponse[PrivateApp]:
        response = await self._transport.request("GET", f"{_PATH}/{validate_id(app_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    async def create_request(self, request: PrivateAppCreate) -> ApiResponse[PrivateApp]:
        payload = request_payload(request, PrivateAppCreate)
        response = await self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    async def update_request(
        self, app_id: int | str, request: PrivateAppPatch
    ) -> ApiResponse[PrivateApp]:
        payload = request_payload(request, PrivateAppPatch)
        response = await self._transport.request(
            "PATCH", f"{_PATH}/{validate_id(app_id)}", json=payload
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateApp))

    async def get_policy_in_use(self, app_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        response = await self._transport.request(
            "POST",
            _POLICY_IN_USE_PATH,
            json={"ids": id_strings(app_ids, "app_ids")},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: PrivateAppPolicyUsage.model_validate(raw.json()))

    async def get_discovery_settings(self) -> ApiResponse[PrivateAppDiscoverySettings]:
        response = await self._transport.request("GET", _DISCOVERY_PATH)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PrivateAppDiscoverySettings)
        )

    async def update_discovery_settings(
        self, request: PrivateAppDiscoveryRequest
    ) -> ApiResponse[PrivateAppDiscoverySettings]:
        payload = request_payload(request, PrivateAppDiscoveryRequest)
        response = await self._transport.request("POST", _DISCOVERY_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_item(raw.json(), PrivateAppDiscoverySettings)
        )

    async def add_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = await self._transport.request("PATCH", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    async def replace_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = await self._transport.request("PUT", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )


class PrivateAppTagResponses(SyncResource):
    """Same-request private-app results with explicit typed decoding."""

    def list_page(
        self, *, query: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[PrivateAppTag]]:
        params = page_params(limit, offset)
        if query is not None:
            params["query"] = query
        response = self._transport.request("GET", _TAGS_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), PrivateAppTag, limit, offset, "tags")
        )

    def get(self, tag_id: int) -> ApiResponse[PrivateAppTag]:
        response = self._transport.request("GET", f"{_TAGS_PATH}/{validate_id(tag_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateAppTag))

    def create(self, app_id: int | str, tag_names: list[str]) -> ApiResponse[list[PrivateAppTag]]:
        payload = _tag_create_payload(app_id, tag_names)
        response = self._transport.request("POST", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateAppTag, "tags")
        )

    def update(self, tag_id: int, tag_name: str) -> ApiResponse[PrivateAppTag]:
        response = self._transport.request(
            "PUT", f"{_TAGS_PATH}/{validate_id(tag_id)}", json={"tag_name": tag_name}
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateAppTag))

    def add(self, app_ids: list[int | str], tag_names: list[str]) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = self._transport.request("PATCH", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    def replace(
        self, app_ids: list[int | str], tag_names: list[str]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = self._transport.request("PUT", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    def get_policy_in_use(self, tag_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        response = self._transport.request(
            "POST",
            _TAGS_POLICY_IN_USE_PATH,
            json={"ids": id_strings(tag_ids, "tag_ids")},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: PrivateAppPolicyUsage.model_validate(raw.json()))


class AsyncPrivateAppTagResponses(AsyncResource):
    """Same-request private-app results with explicit typed decoding."""

    async def list_page(
        self, *, query: str | None = None, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[PrivateAppTag]]:
        params = page_params(limit, offset)
        if query is not None:
            params["query"] = query
        response = await self._transport.request("GET", _TAGS_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: parse_page(raw.json(), PrivateAppTag, limit, offset, "tags")
        )

    async def get(self, tag_id: int) -> ApiResponse[PrivateAppTag]:
        response = await self._transport.request("GET", f"{_TAGS_PATH}/{validate_id(tag_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateAppTag))

    async def create(
        self, app_id: int | str, tag_names: list[str]
    ) -> ApiResponse[list[PrivateAppTag]]:
        payload = _tag_create_payload(app_id, tag_names)
        response = await self._transport.request("POST", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateAppTag, "tags")
        )

    async def update(self, tag_id: int, tag_name: str) -> ApiResponse[PrivateAppTag]:
        response = await self._transport.request(
            "PUT", f"{_TAGS_PATH}/{validate_id(tag_id)}", json={"tag_name": tag_name}
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PrivateAppTag))

    async def add(
        self, app_ids: list[int | str], tag_names: list[str]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = await self._transport.request("PATCH", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    async def replace(
        self, app_ids: list[int | str], tag_names: list[str]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = await self._transport.request("PUT", _TAGS_PATH, json=payload)
        return ApiResponse(
            response, lambda raw: parse_response_list(raw.json(), PrivateApp, "private_apps")
        )

    async def get_policy_in_use(self, tag_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        response = await self._transport.request(
            "POST",
            _TAGS_POLICY_IN_USE_PATH,
            json={"ids": id_strings(tag_ids, "tag_ids")},
            retry_safe=True,
        )
        return ApiResponse(response, lambda raw: PrivateAppPolicyUsage.model_validate(raw.json()))
