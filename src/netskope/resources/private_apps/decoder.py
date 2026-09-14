"""Typed private-app responses, preserving legacy iterator and dictionary APIs."""

from __future__ import annotations

from netskope.core.ids import id_strings, validate_id
from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import parse_response_list
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
from netskope.resources.private_apps.paths import (
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
from netskope.resources.shared.npa import page_params, parse_item, parse_page
from netskope.response import ApiResponse


def _carries_a_collection(body: object) -> bool:
    """Whether the envelope holds a record list at either level it may use."""
    if isinstance(body, list):
        return True
    if not isinstance(body, dict):
        return False
    for value in body.values():
        if isinstance(value, list):
            return True
        if isinstance(value, dict) and any(isinstance(item, list) for item in value.values()):
            return True
    return False


def _parse_association(body: object) -> list[PrivateApp]:
    """Decode a publisher-association acknowledgement.

    ``npa_private_publisher.yaml:167-178`` declares the 200 as
    ``{data: [private_apps_response_item], status}`` and marks neither property
    required, so an acknowledgement carrying only ``status: success`` is
    schema-legal. Treat an absent collection as "no apps reported" rather than
    refusing a response the gateway returned successfully.
    """
    if not _carries_a_collection(body):
        return []
    return parse_response_list(body, PrivateApp, "private_apps")


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
    ) -> ApiResponse[list[PrivateApp] | None]:
        """Remove publisher associations; parses the private apps the API returns.

        ``DELETE /apps/private/publishers`` declares its 200 as
        ``{data: [private_apps_response_item], status}``
        (``npa_private_publisher.yaml:167-178``); byte-identical to the PATCH
        and PUT on the same path, which :meth:`add_publishers` and
        :meth:`replace_publishers` already decode as ``list[PrivateApp]``.  A
        body-less answer (the operation declares no 204, but a tenant may send
        one) parses to ``None`` rather than an empty association list.
        """
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = self._transport.request("DELETE", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: _parse_association(raw.json()) if raw.content else None,
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
        # ``rbac.access: rw`` (npa_apps_private.yaml:735-740): not replay-safe.
        response = self._transport.request(
            "POST", _POLICY_IN_USE_PATH, json={"ids": id_strings(app_ids, "app_ids")}
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
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    def replace_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = self._transport.request("PUT", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))


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
    ) -> ApiResponse[list[PrivateApp] | None]:
        """Remove publisher associations.  See :meth:`PrivateAppResponses.remove_publishers`."""
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = await self._transport.request("DELETE", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(
            response,
            lambda raw: _parse_association(raw.json()) if raw.content else None,
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
        # ``rbac.access: rw`` (npa_apps_private.yaml:735-740): not replay-safe.
        response = await self._transport.request(
            "POST", _POLICY_IN_USE_PATH, json={"ids": id_strings(app_ids, "app_ids")}
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
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    async def replace_publishers(
        self, app_ids: list[int], publisher_ids: list[int]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _publisher_assoc_payload(app_ids, publisher_ids)
        response = await self._transport.request("PUT", _PUBLISHERS_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))


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
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    def replace(
        self, app_ids: list[int | str], tag_names: list[str]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = self._transport.request("PUT", _TAGS_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    def get_policy_in_use(self, tag_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        # ``rbac.access: rw`` (npa_private_tag.yaml:487-492): not replay-safe.
        response = self._transport.request(
            "POST", _TAGS_POLICY_IN_USE_PATH, json={"ids": id_strings(tag_ids, "tag_ids")}
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
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    async def replace(
        self, app_ids: list[int | str], tag_names: list[str]
    ) -> ApiResponse[list[PrivateApp]]:
        payload = _tag_bulk_payload(app_ids, tag_names)
        response = await self._transport.request("PUT", _TAGS_PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_association(raw.json()))

    async def get_policy_in_use(self, tag_ids: list[int]) -> ApiResponse[PrivateAppPolicyUsage]:
        # ``rbac.access: rw`` (npa_private_tag.yaml:487-492): not replay-safe.
        response = await self._transport.request(
            "POST", _TAGS_POLICY_IN_USE_PATH, json={"ids": id_strings(tag_ids, "tag_ids")}
        )
        return ApiResponse(response, lambda raw: PrivateAppPolicyUsage.model_validate(raw.json()))
