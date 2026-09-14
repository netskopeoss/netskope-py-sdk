"""Public CCI response accessors backed by explicit typed contracts."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.core.pagination import Page, build_page, coerce_total
from netskope.core.resource import AsyncResource, SyncResource
from netskope.core.response_list import parse_response_list
from netskope.exceptions import PaginationError, ValidationError
from netskope.models.cci import (
    CciApplication,
    CciAppQuery,
    CciAppTagMap,
    CciTagCreate,
    CciTagDetails,
    CciTagMutationReceipt,
    CciTagName,
    CciTagPatch,
)
from netskope.resources.cci.paths import (
    _APP_PATH,
    _TAGS_ALL_PATH,
    _TAGS_PATH,
    _TAGS_RULES_PATH,
    _app_query_params,
    _build_tag_list_params,
    _tag_path,
)
from netskope.response import ApiResponse

T = TypeVar("T", bound=BaseModel)


def _request(request: T, model: type[T]) -> T:
    try:
        return model.model_validate(request)
    except ModelValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) or "request" for error in exc.errors())
        raise ValidationError(f"Invalid CCI request fields: {fields}.") from None


def _app_params(query: CciAppQuery) -> dict[str, Any]:
    return _app_query_params(_request(query, CciAppQuery))


def _page(
    response: httpx.Response, model: type[T], limit: int | None, offset: int | None, total_key: str
) -> Page[T]:
    if response.status_code == 204 and not response.content:
        return Page(items=[], total=0, offset=offset or 0, limit=limit, has_more=False)
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("Expected a CCI response envelope.")
    if response.status_code == 204:
        return Page(items=[], total=0, offset=offset or 0, limit=limit, has_more=False)
    return build_page(
        parse_response_list(body, model),
        offset=offset or 0,
        limit=limit,
        total=coerce_total(body.get(total_key)),
        metadata={key: value for key, value in body.items() if key != "data"},
        # The application query echoes the offset it served; the rules query does not.
        echoed_offset=body.get("offset"),
    )


def _names(response: httpx.Response) -> Page[CciTagName]:
    if response.status_code == 204 and not response.content:
        return Page(items=[], total=0, offset=0, limit=None, has_more=False)
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if response.status_code == 204 and data == {}:
        return Page(items=[], total=0, offset=0, limit=None, has_more=False)
    if not isinstance(data, dict) or not isinstance(data.get("tags"), list):
        raise ValueError("Expected the CCI tag-name catalog.")
    items = [CciTagName.model_validate(name) for name in data["tags"]]
    total = len(items)
    stated = coerce_total(data.get("tags_count"))
    if stated is not None and stated != total:
        raise PaginationError("The CCI tag catalog contradicts its count.", offset=0)
    return Page(items=items, total=total, offset=0, limit=None, has_more=False)


def _app_tags(response: httpx.Response) -> CciAppTagMap:
    if response.status_code == 204 and not response.content:
        return CciAppTagMap({})
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise ValueError("Expected CCI tag memberships by application.")
    return CciAppTagMap.model_validate(body["data"])


def _receipt(response: httpx.Response) -> CciTagMutationReceipt | None:
    return CciTagMutationReceipt.model_validate(response.json()) if response.content else None


def _list_membership_params(apps: list[str] | None, ids: list[str] | None) -> dict[str, Any]:
    if (apps is None) == (ids is None):
        raise ValidationError("Provide exactly one of apps or ids.")
    selected = apps if apps is not None else ids
    if (
        not selected
        or len(selected) > 100
        or any(
            not isinstance(value, str) or not value.strip() or ";" in value for value in selected
        )
    ):
        raise ValidationError("Provide 1 to 100 application names or IDs.")
    params = _build_tag_list_params(apps, [*ids] if ids is not None else None)
    if params is None:
        raise ValidationError("Provide exactly one of apps or ids.")
    return params


def _delete_params(tag: str) -> dict[str, str]:
    _tag_path(tag)
    if "," in tag:
        raise ValidationError("A single tag name must not contain a comma.")
    return {"tags": tag}


def _patch_payload(tag: str, request: CciTagPatch) -> dict[str, Any]:
    if tag in ("Sanctioned", "Unsanctioned", "Departmental", "Enterprise", "Consumer"):
        raise ValidationError(
            "Explicit append/remove actions are not supported for predefined CCI tags."
        )
    return _request(request, CciTagPatch).model_dump(mode="json", by_alias=True, exclude_unset=True)


class CciResponses(SyncResource):
    """Typed, bounded CCI application reads."""

    def list_page(self, query: CciAppQuery) -> ApiResponse[Page[CciApplication]]:
        params = _app_params(query)
        response = self._transport.request("GET", _APP_PATH, params=params)
        return ApiResponse(
            response,
            lambda raw: _page(raw, CciApplication, query.limit, query.offset, "total_query_count"),
        )


class CciTagResponses(SyncResource):
    """Typed tag names, memberships, rule details and mutation receipts."""

    def list_names_page(self) -> ApiResponse[Page[CciTagName]]:
        response = self._transport.request("GET", _TAGS_ALL_PATH)
        return ApiResponse(response, _names)

    def list_by_apps(
        self, *, apps: list[str] | None = None, ids: list[str] | None = None
    ) -> ApiResponse[CciAppTagMap]:
        params = _list_membership_params(apps, ids)
        response = self._transport.request("GET", _TAGS_PATH, params=params)
        return ApiResponse(response, _app_tags)

    def list_rules_page(
        self,
        *,
        tag: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[CciTagDetails]]:
        params: dict[str, Any] = {}
        for key, value in (("limit", limit), ("offset", offset)):
            if value is not None:
                if type(value) is not int or value < 0:
                    raise ValidationError(f"{key} must be a nonnegative integer.")
                params[key] = value
        if tag is not None:
            _tag_path(tag)
            params["tag"] = tag
        response = self._transport.request("GET", _TAGS_RULES_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: _page(raw, CciTagDetails, limit, offset, "tags_count")
        )

    def create_request(self, request: CciTagCreate) -> ApiResponse[CciTagMutationReceipt | None]:
        payload = _request(request, CciTagCreate).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        response = self._transport.request("POST", _TAGS_PATH, json=payload)
        return ApiResponse(response, _receipt)

    def update_request(
        self, tag: str, request: CciTagPatch
    ) -> ApiResponse[CciTagMutationReceipt | None]:
        payload = _patch_payload(tag, request)
        response = self._transport.request("PATCH", _tag_path(tag), json=payload)
        return ApiResponse(response, _receipt)

    def delete(self, tag: str) -> ApiResponse[CciTagMutationReceipt | None]:
        params = _delete_params(tag)
        response = self._transport.request("DELETE", _TAGS_PATH, params=params)
        return ApiResponse(response, _receipt)


class AsyncCciResponses(AsyncResource):
    """Typed, bounded CCI application reads."""

    async def list_page(self, query: CciAppQuery) -> ApiResponse[Page[CciApplication]]:
        params = _app_params(query)
        response = await self._transport.request("GET", _APP_PATH, params=params)
        return ApiResponse(
            response,
            lambda raw: _page(raw, CciApplication, query.limit, query.offset, "total_query_count"),
        )


class AsyncCciTagResponses(AsyncResource):
    """Typed tag names, memberships, rule details and mutation receipts."""

    async def list_names_page(self) -> ApiResponse[Page[CciTagName]]:
        response = await self._transport.request("GET", _TAGS_ALL_PATH)
        return ApiResponse(response, _names)

    async def list_by_apps(
        self, *, apps: list[str] | None = None, ids: list[str] | None = None
    ) -> ApiResponse[CciAppTagMap]:
        params = _list_membership_params(apps, ids)
        response = await self._transport.request("GET", _TAGS_PATH, params=params)
        return ApiResponse(response, _app_tags)

    async def list_rules_page(
        self,
        *,
        tag: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[CciTagDetails]]:
        params: dict[str, Any] = {}
        for key, value in (("limit", limit), ("offset", offset)):
            if value is not None:
                if type(value) is not int or value < 0:
                    raise ValidationError(f"{key} must be a nonnegative integer.")
                params[key] = value
        if tag is not None:
            _tag_path(tag)
            params["tag"] = tag
        response = await self._transport.request("GET", _TAGS_RULES_PATH, params=params or None)
        return ApiResponse(
            response, lambda raw: _page(raw, CciTagDetails, limit, offset, "tags_count")
        )

    async def create_request(
        self, request: CciTagCreate
    ) -> ApiResponse[CciTagMutationReceipt | None]:
        payload = _request(request, CciTagCreate).model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
        response = await self._transport.request("POST", _TAGS_PATH, json=payload)
        return ApiResponse(response, _receipt)

    async def update_request(
        self, tag: str, request: CciTagPatch
    ) -> ApiResponse[CciTagMutationReceipt | None]:
        payload = _patch_payload(tag, request)
        response = await self._transport.request("PATCH", _tag_path(tag), json=payload)
        return ApiResponse(response, _receipt)

    async def delete(self, tag: str) -> ApiResponse[CciTagMutationReceipt | None]:
        params = _delete_params(tag)
        response = await self._transport.request("DELETE", _TAGS_PATH, params=params)
        return ApiResponse(response, _receipt)
