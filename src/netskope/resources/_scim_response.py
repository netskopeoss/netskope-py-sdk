"""One-request typed SCIM provisioning, including empty PATCH acknowledgments."""

from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import PaginationError, ValidationError
from netskope.models.scim import (
    ScimGroup,
    ScimGroupCreate,
    ScimGroupPatch,
    ScimUser,
    ScimUserCreate,
    ScimUserPatch,
)
from netskope.pagination import Page
from netskope.resources._admin_response import page, page_params
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id
from netskope.response import ApiResponse

T = TypeVar("T", bound=BaseModel)
_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
_MAX_COUNT = 1000


def validate_page_size(page_size: int) -> int:
    """Bound an iterator page size by the same maximum a single ``count`` allows."""
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= _MAX_COUNT
    ):
        raise ValidationError(f"page_size must be an integer between 1 and {_MAX_COUNT}.")
    return page_size


def _scim_params(filter_expr: str | None, count: int, start_index: int) -> dict[str, Any]:
    # RFC 7644 allows count=0 as a totals-only probe; only the ceiling was missing.
    page_params(count, start_index, maximum=_MAX_COUNT)
    if start_index < 1:
        raise ValidationError("start_index must be at least 1.")
    params: dict[str, Any] = {"count": count, "startIndex": start_index}
    if filter_expr is not None:
        params["filter"] = filter_expr
    return params


def _scim_page(response: httpx.Response, model: type[T], count: int, start_index: int) -> Page[T]:
    body = response.json()
    if isinstance(body, dict) and "startIndex" in body:
        value = body["startIndex"]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, str))
            or str(value) != str(start_index)
        ):
            raise PaginationError(
                "The SCIM response startIndex does not match the requested page.",
                offset=start_index - 1,
            )
    return page(
        response, model, "Resources", limit=count, offset=start_index - 1, total_key="totalResults"
    )


def _validated(request: T, model: type[T]) -> T:
    try:
        return model.model_validate(request)
    except ModelValidationError:
        raise ValidationError("Invalid SCIM provisioning request.") from None


def _user_create(request: ScimUserCreate) -> dict[str, Any]:
    request = _validated(request, ScimUserCreate)
    return {
        "schemas": [_USER_SCHEMA],
        "userName": request.user_name,
        "active": request.active,
        "emails": [{"value": request.email, "primary": True}],
    }


def _group_create(request: ScimGroupCreate) -> dict[str, Any]:
    request = _validated(request, ScimGroupCreate)
    body: dict[str, Any] = {"schemas": [_GROUP_SCHEMA], "displayName": request.display_name}
    if request.member_ids is not None:
        body["members"] = [{"value": value} for value in request.member_ids]
    return body


def _user_patch(request: ScimUserPatch) -> dict[str, Any]:
    request = _validated(request, ScimUserPatch)
    return {
        "schemas": [_PATCH_SCHEMA],
        "Operations": [
            {"op": "replace", "path": key, "value": value} for key, value in request.fields.items()
        ],
    }


def _group_patch(request: ScimGroupPatch) -> dict[str, Any]:
    request = _validated(request, ScimGroupPatch)
    operations: list[dict[str, Any]] = []
    if request.display_name is not None:
        operations.append({"op": "replace", "path": "displayName", "value": request.display_name})
    if request.member_ids is not None:
        operations.append(
            {
                "op": "replace",
                "path": "members",
                "value": [{"value": value} for value in request.member_ids],
            }
        )
    return {"schemas": [_PATCH_SCHEMA], "Operations": operations}


def _patch_result(response: httpx.Response, model: type[T]) -> T | None:
    if not response.content and response.status_code == 204:
        return None
    return model.model_validate(response.json())


class ScimUsersResponses(SyncResource):
    def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> ApiResponse[Page[ScimUser]]:
        params = _scim_params(filter_expr, count, start_index)
        response = self._transport.request("GET", "/api/v2/scim/Users", params=params)
        return ApiResponse(response, lambda raw: _scim_page(raw, ScimUser, count, start_index))

    def create(self, request: ScimUserCreate) -> ApiResponse[ScimUser]:
        response = self._transport.request("POST", "/api/v2/scim/Users", json=_user_create(request))
        return ApiResponse(response, lambda raw: ScimUser.model_validate(raw.json()))

    def patch(self, user_id: str, request: ScimUserPatch) -> ApiResponse[ScimUser | None]:
        path = f"/api/v2/scim/Users/{quote_id(user_id)}"
        response = self._transport.request("PATCH", path, json=_user_patch(request))
        return ApiResponse(response, lambda raw: _patch_result(raw, ScimUser))

    def delete(self, user_id: str) -> None:
        self._transport.request("DELETE", f"/api/v2/scim/Users/{quote_id(user_id)}")


class ScimGroupsResponses(SyncResource):
    def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> ApiResponse[Page[ScimGroup]]:
        params = _scim_params(filter_expr, count, start_index)
        response = self._transport.request("GET", "/api/v2/scim/Groups", params=params)
        return ApiResponse(response, lambda raw: _scim_page(raw, ScimGroup, count, start_index))

    def create(self, request: ScimGroupCreate) -> ApiResponse[ScimGroup]:
        response = self._transport.request(
            "POST", "/api/v2/scim/Groups", json=_group_create(request)
        )
        return ApiResponse(response, lambda raw: ScimGroup.model_validate(raw.json()))

    def patch(self, group_id: str, request: ScimGroupPatch) -> ApiResponse[ScimGroup | None]:
        path = f"/api/v2/scim/Groups/{quote_id(group_id)}"
        response = self._transport.request("PATCH", path, json=_group_patch(request))
        return ApiResponse(response, lambda raw: _patch_result(raw, ScimGroup))

    def delete(self, group_id: str) -> None:
        self._transport.request("DELETE", f"/api/v2/scim/Groups/{quote_id(group_id)}")


class AsyncScimUsersResponses(AsyncResource):
    async def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> ApiResponse[Page[ScimUser]]:
        params = _scim_params(filter_expr, count, start_index)
        response = await self._transport.request("GET", "/api/v2/scim/Users", params=params)
        return ApiResponse(response, lambda raw: _scim_page(raw, ScimUser, count, start_index))

    async def create(self, request: ScimUserCreate) -> ApiResponse[ScimUser]:
        response = await self._transport.request(
            "POST", "/api/v2/scim/Users", json=_user_create(request)
        )
        return ApiResponse(response, lambda raw: ScimUser.model_validate(raw.json()))

    async def patch(self, user_id: str, request: ScimUserPatch) -> ApiResponse[ScimUser | None]:
        path = f"/api/v2/scim/Users/{quote_id(user_id)}"
        response = await self._transport.request("PATCH", path, json=_user_patch(request))
        return ApiResponse(response, lambda raw: _patch_result(raw, ScimUser))

    async def delete(self, user_id: str) -> None:
        await self._transport.request("DELETE", f"/api/v2/scim/Users/{quote_id(user_id)}")


class AsyncScimGroupsResponses(AsyncResource):
    async def list_page(
        self, *, filter_expr: str | None = None, count: int = 100, start_index: int = 1
    ) -> ApiResponse[Page[ScimGroup]]:
        params = _scim_params(filter_expr, count, start_index)
        response = await self._transport.request("GET", "/api/v2/scim/Groups", params=params)
        return ApiResponse(response, lambda raw: _scim_page(raw, ScimGroup, count, start_index))

    async def create(self, request: ScimGroupCreate) -> ApiResponse[ScimGroup]:
        response = await self._transport.request(
            "POST", "/api/v2/scim/Groups", json=_group_create(request)
        )
        return ApiResponse(response, lambda raw: ScimGroup.model_validate(raw.json()))

    async def patch(self, group_id: str, request: ScimGroupPatch) -> ApiResponse[ScimGroup | None]:
        path = f"/api/v2/scim/Groups/{quote_id(group_id)}"
        response = await self._transport.request("PATCH", path, json=_group_patch(request))
        return ApiResponse(response, lambda raw: _patch_result(raw, ScimGroup))

    async def delete(self, group_id: str) -> None:
        await self._transport.request("DELETE", f"/api/v2/scim/Groups/{quote_id(group_id)}")
