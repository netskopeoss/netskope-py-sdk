"""Typed URL-list response accessors, preserving update's existing read-merge-write."""

from __future__ import annotations

from typing import Any

from netskope._pagination import _make_page
from netskope.models.url_lists import PolicyDeployment, UrlList
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._npa_response import page_params
from netskope.resources._response_list import extract_response_list
from netskope.resources.url_lists import (
    _DEPLOY_PATH,
    _PATH,
    _flatten_url_list,
    _list_path,
    _merge_source,
    _payload,
    _require_record,
    _update_fields,
)
from netskope.response import ApiResponse


def _parse_item(body: Any) -> UrlList:
    return UrlList.model_validate(_require_record(body))


def _parse_page(body: Any, limit: int | None, offset: int | None) -> Page[UrlList]:
    rows = extract_response_list(body, "urllists")
    items = [UrlList.model_validate(_flatten_url_list(row)) for row in rows]
    metadata = (
        {key: value for key, value in body.items() if key not in ("data", "result", "urllists")}
        if isinstance(body, dict)
        else {}
    )
    return _make_page(items, metadata, offset or 0, limit)


class UrlListResponses(SyncResource):
    """Completed typed URL-list responses."""

    def list_page(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[UrlList]]:
        response = self._transport.request("GET", _PATH, params=page_params(limit, offset) or None)
        return ApiResponse(response, lambda raw: _parse_page(raw.json(), limit, offset))

    def get(self, list_id: int) -> ApiResponse[UrlList]:
        response = self._transport.request("GET", _list_path(list_id))
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    def create(
        self, name: str, urls: list[str], *, list_type: str = "exact"
    ) -> ApiResponse[UrlList]:
        payload = _payload(name, urls, list_type)
        response = self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: list[str] | None = None,
        list_type: str | None = None,
    ) -> ApiResponse[UrlList]:
        _update_fields(name, urls, list_type)
        current = _merge_source(self.get(list_id).parse(), list_id)
        payload = _payload(
            name if name is not None else (current.name or ""),
            urls if urls is not None else current.urls,
            list_type if list_type is not None else (current.type or "exact"),
        )
        response = self._transport.request("PUT", _list_path(list_id), json=payload)
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    def deploy(self) -> ApiResponse[PolicyDeployment]:
        response = self._transport.request("POST", _DEPLOY_PATH)
        return ApiResponse(response, lambda raw: PolicyDeployment.model_validate(raw.json()))

    def delete(self, list_id: int) -> ApiResponse[PolicyDeployment | None]:
        response = self._transport.request("DELETE", _list_path(list_id))
        return ApiResponse(
            response,
            lambda raw: PolicyDeployment.model_validate(raw.json()) if raw.content else None,
        )


class AsyncUrlListResponses(AsyncResource):
    """Completed typed URL-list responses."""

    async def list_page(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[UrlList]]:
        response = await self._transport.request(
            "GET", _PATH, params=page_params(limit, offset) or None
        )
        return ApiResponse(response, lambda raw: _parse_page(raw.json(), limit, offset))

    async def get(self, list_id: int) -> ApiResponse[UrlList]:
        response = await self._transport.request("GET", _list_path(list_id))
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    async def create(
        self, name: str, urls: list[str], *, list_type: str = "exact"
    ) -> ApiResponse[UrlList]:
        payload = _payload(name, urls, list_type)
        response = await self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    async def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: list[str] | None = None,
        list_type: str | None = None,
    ) -> ApiResponse[UrlList]:
        _update_fields(name, urls, list_type)
        current = _merge_source((await self.get(list_id)).parse(), list_id)
        payload = _payload(
            name if name is not None else (current.name or ""),
            urls if urls is not None else current.urls,
            list_type if list_type is not None else (current.type or "exact"),
        )
        response = await self._transport.request("PUT", _list_path(list_id), json=payload)
        return ApiResponse(response, lambda raw: _parse_item(raw.json()))

    async def deploy(self) -> ApiResponse[PolicyDeployment]:
        response = await self._transport.request("POST", _DEPLOY_PATH)
        return ApiResponse(response, lambda raw: PolicyDeployment.model_validate(raw.json()))

    async def delete(self, list_id: int) -> ApiResponse[PolicyDeployment | None]:
        response = await self._transport.request("DELETE", _list_path(list_id))
        return ApiResponse(
            response,
            lambda raw: PolicyDeployment.model_validate(raw.json()) if raw.content else None,
        )
