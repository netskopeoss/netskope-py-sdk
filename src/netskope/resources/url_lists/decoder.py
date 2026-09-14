"""Typed URL-list response accessors, preserving update's existing read-merge-write."""

from __future__ import annotations

from typing import Any

from netskope.core.pagination import Page, local_page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import extract_response_list
from netskope.models.url_lists import PolicyDeployment, UrlList
from netskope.resources.shared.npa import page_params
from netskope.resources.url_lists.paths import (
    _DEPLOY_PATH,
    _PATH,
    _build_list_params,
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


def _deployed(row: Any) -> UrlList:
    """Validate one deployed record, flattening its nested ``data`` first.

    A URL-list record carries ``urls``/``type`` under ``data``; without the
    flattening every sibling decoder applies, the declared fields come back
    empty and the payload is stranded in ``model_extra``.
    """
    return UrlList.model_validate(_flatten_url_list(row) if isinstance(row, dict) else row)


def _parse_deployment(body: Any) -> PolicyDeployment:
    """Decode the deploy acknowledgment from either shape the API answers with.

    ``POST /urllist/deploy`` returns the array of URL lists it applied
    (policy/urllist.yaml:209-217), which carries no status of its own, so the
    records land in ``PolicyDeployment.urllists``.  An object response keeps
    its ``status``/``message``.
    """
    if isinstance(body, list):
        return PolicyDeployment(urllists=[_deployed(row) for row in body])
    deployment = PolicyDeployment.model_validate(body)
    if not deployment.urllists:
        # A `{data: [...], status}` envelope keeps its status on the model but
        # leaves the records unread, because `urllists` is the only collection
        # key the model declares. Read them the way every other decoder here
        # does rather than stranding them in `model_extra`.
        rows = extract_response_list(body, "urllists")
        if rows:
            deployment = deployment.model_copy(update={"urllists": [_deployed(r) for r in rows]})
    return deployment


def _parse_page(body: Any, limit: int | None, offset: int | None) -> Page[UrlList]:
    """Decode the whole collection and window it locally.

    ``GET /urllist`` declares only ``pending`` and ``field``
    (``policy/urllist.yaml:132-156``), so a requested window cannot be sent and
    is applied to the records in hand; see :func:`netskope.core.pagination.local_page`.
    """
    rows = extract_response_list(body, "urllists")
    items = [UrlList.model_validate(_flatten_url_list(row)) for row in rows]
    metadata = (
        {key: value for key, value in body.items() if key not in ("data", "result", "urllists")}
        if isinstance(body, dict)
        else {}
    )
    return local_page(items, metadata, offset or 0, limit)


class UrlListResponses(SyncResource):
    """Completed typed URL-list responses."""

    def list_page(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[UrlList]]:
        """Fetch the collection and window it locally by *offset*/*limit*.

        ``GET /urllist`` declares neither parameter
        (``policy/urllist.yaml:132-156``), so only ``pending``/``field`` are
        sent and the window is applied to the records the gateway returns.
        """
        # ``page_params`` is called for its validation only: neither parameter is
        # declared by this operation, so the window is applied locally below.
        page_params(limit, offset)
        params = _build_list_params(pending, field)
        response = self._transport.request("GET", _PATH, params=params or None)
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
        return ApiResponse(response, lambda raw: _parse_deployment(raw.json()))

    def delete(self, list_id: int) -> ApiResponse[UrlList | None]:
        """Mark a URL list pending deletion; parses the record the API returns.

        ``DELETE /urllist/{id}`` declares its 200 as ``DeletedUrllist``
        (``policy/urllist.yaml:276-281`` → ``:3-35``); the full URL-list record
        with ``modify_type: Deleted`` and ``pending: 1``, not a deployment
        acknowledgment.  A body-less response parses to ``None``.
        """
        response = self._transport.request("DELETE", _list_path(list_id))
        return ApiResponse(response, lambda raw: _parse_item(raw.json()) if raw.content else None)


class AsyncUrlListResponses(AsyncResource):
    """Completed typed URL-list responses."""

    async def list_page(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[UrlList]]:
        """Fetch and window the collection locally.  See :meth:`UrlListResponses.list_page`."""
        # ``page_params`` is called for its validation only: neither parameter is
        # declared by this operation, so the window is applied locally below.
        page_params(limit, offset)
        params = _build_list_params(pending, field)
        response = await self._transport.request("GET", _PATH, params=params or None)
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
        return ApiResponse(response, lambda raw: _parse_deployment(raw.json()))

    async def delete(self, list_id: int) -> ApiResponse[UrlList | None]:
        """Mark a URL list pending deletion.  See :meth:`UrlListResponses.delete`."""
        response = await self._transport.request("DELETE", _list_path(list_id))
        return ApiResponse(response, lambda raw: _parse_item(raw.json()) if raw.content else None)
