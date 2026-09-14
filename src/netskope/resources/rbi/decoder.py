"""Bounded and typed RBI reads, preserving the complete buffered response."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import TypeAdapter

from netskope.core.decoding import decode_body, parse_object_page
from netskope.core.pagination import Page
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.rbi import RbiApplications, RbiBrowser, RbiCategory, RbiTemplate
from netskope.resources.rbi.paths import (
    _APPLICATIONS_PATH,
    _BROWSERS_PATH,
    _CATEGORIES_PATH,
    _TEMPLATES_PATH,
    _template_path,
)
from netskope.response import ApiResponse

_APPS = TypeAdapter(RbiApplications)
_BROWSERS = TypeAdapter(list[RbiBrowser])
_CATEGORIES = TypeAdapter(list[RbiCategory])
_TEMPLATE = TypeAdapter(RbiTemplate)


def _page_params(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key, value in (("limit", limit), ("offset", offset)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"{key} must be a nonnegative integer.")
            params[key] = value
    return params


def _template(response: httpx.Response, template_id: int | str) -> RbiTemplate:
    template = decode_body(response, _TEMPLATE)
    if template.metadata.id != str(template_id):
        raise ValueError("The response identifies a different template.")
    return template


def _page(response: httpx.Response, limit: int | None, offset: int | None) -> Page[RbiTemplate]:
    # `list_templates` documents `limit=0` as "unlimited" and sends it as such,
    # so 0 must not reach `build_page`, which reads a limit as a page-size cap
    # and would reject every non-empty response the caller just asked for.
    return parse_object_page(
        response.json(),
        RbiTemplate,
        records_key="items",
        total_key="total_count",
        offset=offset or 0,
        limit=limit or None,
    )


class RbiResponses(SyncResource):
    """Typed RBI reference data and isolation-template reads, with their buffered responses."""

    def list_applications(self) -> ApiResponse[RbiApplications]:
        response = self._transport.request("GET", _APPLICATIONS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS))

    def list_supported_browsers(self) -> ApiResponse[list[RbiBrowser]]:
        response = self._transport.request("GET", _BROWSERS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _BROWSERS))

    def list_default_categories(self) -> ApiResponse[list[RbiCategory]]:
        response = self._transport.request("GET", _CATEGORIES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _CATEGORIES))

    def list_templates(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[RbiTemplate]]:
        response = self._transport.request(
            "GET", _TEMPLATES_PATH, params=_page_params(limit, offset)
        )
        return ApiResponse(response, lambda raw: _page(raw, limit, offset))

    def get_template(self, template_id: int | str) -> ApiResponse[RbiTemplate]:
        response = self._transport.request("GET", _template_path(template_id))
        return ApiResponse(response, lambda raw: _template(raw, template_id))


class AsyncRbiResponses(AsyncResource):
    """Typed RBI reference data and isolation-template reads, with their buffered responses."""

    async def list_applications(self) -> ApiResponse[RbiApplications]:
        response = await self._transport.request("GET", _APPLICATIONS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _APPS))

    async def list_supported_browsers(self) -> ApiResponse[list[RbiBrowser]]:
        response = await self._transport.request("GET", _BROWSERS_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _BROWSERS))

    async def list_default_categories(self) -> ApiResponse[list[RbiCategory]]:
        response = await self._transport.request("GET", _CATEGORIES_PATH)
        return ApiResponse(response, lambda raw: decode_body(raw, _CATEGORIES))

    async def list_templates(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiResponse[Page[RbiTemplate]]:
        response = await self._transport.request(
            "GET", _TEMPLATES_PATH, params=_page_params(limit, offset)
        )
        return ApiResponse(response, lambda raw: _page(raw, limit, offset))

    async def get_template(self, template_id: int | str) -> ApiResponse[RbiTemplate]:
        response = await self._transport.request("GET", _template_path(template_id))
        return ApiResponse(response, lambda raw: _template(raw, template_id))
