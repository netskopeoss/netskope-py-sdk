"""Paths and payload builders shared by the rbac resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import math
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from netskope.core.ids import extract_item, validate_id
from netskope.core.pagination import (
    Page,
    build_page,
    coerce_total,
)
from netskope.core.response_list import parse_response_list
from netskope.exceptions import PaginationError, ValidationError
from netskope.models.administration import AdminUser
from netskope.models.rbac import (
    RbacRoleDetail,
    RoleCreate,
    RoleMutationReceipt,
    RolePatch,
)
from netskope.resources.scim.decoder import MAX_SCIM_PAGE_SIZE

T = TypeVar("T", bound=BaseModel)


_ROLES_PATH = "/api/v2/rbac/roles"


_ADMINS_PATH = "/api/v2/platform/administration/scim/Users"


_VALID_ROLE_TYPES = ("custom", "predefined")


_VALID_ROLE_SCOPES = ("limited", "no_limit")


_ROLES_LIST_KEY = "roles"


def _role_path_id(role_id: int | float) -> str:
    """Preserve numeric role IDs, including fractions (ms-rbac.yaml:1195-1200)."""
    if isinstance(role_id, float):
        if not math.isfinite(role_id) or role_id < 0:
            raise ValidationError("role_id must be a finite nonnegative number.")
        return str(role_id)
    return validate_id(role_id, "role_id")


def _build_roles_params(
    role_type: str | None,
    scope: str | None,
    search: str | None,
    limit: int | None,
    offset: int | None,
) -> dict[str, Any]:
    """Validate the roles query, whichever accessor asked for it.

    ``RolesController_findAll`` declares ``offset`` and ``limit`` as
    ``type: number`` and bounds the latter in prose; "limit should be between
    1 and 1000" (ms-rbac.yaml:986-997). The bound is checked here rather than
    in one accessor, so a non-numeric ``limit`` cannot reach the query string
    and a non-numeric ``offset`` cannot reach the page arithmetic in
    :func:`_parse_roles_page`.
    """
    if role_type is not None and role_type not in _VALID_ROLE_TYPES:
        raise ValidationError(
            f"Invalid role_type {role_type!r}. Must be one of: {', '.join(_VALID_ROLE_TYPES)}"
        )
    if scope is not None and scope not in _VALID_ROLE_SCOPES:
        raise ValidationError(
            f"Invalid scope {scope!r}. Must be one of: {', '.join(_VALID_ROLE_SCOPES)}"
        )
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000
    ):
        raise ValidationError("Invalid limit: expected an integer between 1 and 1000.")
    if offset is not None and (
        isinstance(offset, bool) or not isinstance(offset, int) or offset < 0
    ):
        raise ValidationError("Invalid offset: expected an integer >= 0.")
    params: dict[str, Any] = {}
    if role_type is not None:
        params["type"] = role_type
    if scope is not None:
        params["scope"] = scope
    if search:
        params["search"] = search
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_admins_params(filter_expr: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr:
        params["filter"] = filter_expr
    return params


def _build_role_request(
    request: RoleCreate | RolePatch, model: type[RoleCreate] | type[RolePatch]
) -> dict[str, Any]:
    try:
        validated = model.model_validate(request)
    except ModelValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(map(str, error['loc'])) or 'request'}: {error['msg']}"
            for error in exc.errors(include_input=False, include_context=False)
        )
        raise ValidationError(f"Invalid role request: {errors}") from None
    return validated.model_dump(mode="json", by_alias=True, exclude_unset=True)


def _parse_role_receipt(body: Any, expected_id: int | float | None = None) -> RoleMutationReceipt:
    receipt = _parse_role(body, RoleMutationReceipt)
    if expected_id is not None and receipt.id != expected_id:
        raise ValueError("The role mutation receipt does not match the requested role.")
    return receipt


def _parse_role_detail(body: Any, expected_id: int | float) -> RbacRoleDetail:
    detail = _parse_role(body, RbacRoleDetail)
    if detail.id != expected_id:
        raise ValueError("The role detail does not match the requested role.")
    return detail


def _build_admins_page_params(
    filter_expr: str | None, count: int, start_index: int
) -> dict[str, Any]:
    for name, value, minimum in (("count", count, 0), ("start_index", start_index, 1)):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValidationError(f"Invalid {name}: expected an integer >= {minimum}.")
    if count > MAX_SCIM_PAGE_SIZE:
        raise ValidationError(f"Invalid count: the maximum SCIM page size is {MAX_SCIM_PAGE_SIZE}.")
    return {**_build_admins_params(filter_expr), "count": count, "startIndex": start_index}


def _parse_roles_page(body: Any, model: type[T], offset: int, limit: int | None) -> Page[T]:
    items = parse_response_list(body, model, _ROLES_LIST_KEY)
    metadata = dict(body) if isinstance(body, dict) else {}
    if isinstance(metadata.get("result"), list):
        metadata.pop("result")
    elif isinstance(metadata.get("data"), list):
        metadata.pop("data")
    elif isinstance(metadata.get("data"), dict) and _ROLES_LIST_KEY in metadata["data"]:
        nested = dict(metadata["data"])
        nested.pop(_ROLES_LIST_KEY)
        if nested:
            metadata["data"] = nested
        else:
            metadata.pop("data")
    elif _ROLES_LIST_KEY in metadata:
        metadata.pop(_ROLES_LIST_KEY)
    elif "Resources" in metadata:
        metadata.pop("Resources")
    # GetRolesResponseDto requires ``count`` and documents it as the total number
    # of roles fitting the search criteria (ms-rbac.yaml:1670-1687), so it is this
    # page's total. It is deliberately not used to reject records the way
    # build_page does: no live tenant has confirmed whether the service counts the
    # filtered collection or only the page it returned, and guessing wrong there
    # would turn ordinary second-page traversal into an error.
    total = coerce_total(metadata.get("count"))
    return Page(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        metadata=metadata,
        has_more=None if total is None else offset + len(items) < total,
    )


def _parse_role(body: Any, model: type[T]) -> T:
    if not isinstance(body, dict) or not body:
        raise ValueError("Invalid role response: expected a role object.")
    if "data" in body:
        data = body["data"]
        if not isinstance(data, dict) and not (
            isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict)
        ):
            raise ValueError("Invalid role response: expected one role object.")
    record = extract_item(body)
    if not record:
        raise ValueError("Invalid role response: expected a nonempty role object.")
    return model.model_validate(record)


def _parse_admins_page(body: Any, start_index: int, count: int) -> Page[AdminUser]:
    if not isinstance(body, dict):
        raise ValueError("Invalid admin response: expected a SCIM Resources collection.")
    if not isinstance(body.get("Resources"), list):
        # RFC 7644 3.4.2 requires `Resources` only once `totalResults` is
        # non-zero, so a search that matched nothing may omit it. A non-zero
        # total with no collection stays an error: reading it as an empty page
        # would silently lose records.
        if str(body.get("totalResults")) != "0":
            raise ValueError("Invalid admin response: expected a SCIM Resources collection.")
        body = {**body, "Resources": []}
    if len(body["Resources"]) > count:
        raise PaginationError(
            "The admin response exceeded the requested page size.", offset=start_index - 1
        )
    items = parse_response_list(body["Resources"], AdminUser)
    metadata = {key: value for key, value in body.items() if key != "Resources"}
    returned_index = metadata.get("startIndex", start_index)
    if (
        isinstance(returned_index, bool)
        or not isinstance(returned_index, (int, str))
        or str(returned_index) != str(start_index)
    ):
        raise PaginationError(
            "Invalid admin response: startIndex does not match the requested page.",
            offset=start_index - 1,
        )
    return build_page(
        items,
        offset=start_index - 1,
        limit=count,
        total=coerce_total(metadata.get("totalResults")),
        metadata=metadata,
    )
