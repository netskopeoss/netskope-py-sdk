"""Verified DSPM routes and same-request typed responses.

The legacy raw methods retain their historical paths. This surface only maps
resource names whose semantics are present in dspm_external.yaml at the pinned
gateway contract revision documented in the migration plan.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError as ModelValidationError

from netskope._pagination import build_page, coerce_total
from netskope.exceptions import ValidationError
from netskope.models.dspm import (
    DspmCategory,
    DspmClassificationColumn,
    DspmClassificationFile,
    DspmDatabaseObject,
    DspmDatastore,
    DspmDataTag,
    DspmInfrastructureConnection,
    DspmRecord,
    DspmResourceType,
    DspmScanRequest,
    DspmSensitiveDataType,
    DspmSidecarPool,
    SortOrder,
)
from netskope.pagination import Page
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources.dspm import _build_list_params, _validate_resource_type
from netskope.response import ApiResponse

_ROUTES: dict[str, tuple[str, type[DspmRecord]]] = {
    "connected_datastores": ("/datastores/connected", DspmDatastore),
    "discovered_datastores": ("/datastores/discovered", DspmDatastore),
    "archived_datastores": ("/datastores/archived", DspmDatastore),
    "databases": ("/datastores/connected/databases", DspmDatabaseObject),
    "schemas": ("/datastores/connected/schemas", DspmDatabaseObject),
    "tables": ("/datastores/connected/tables", DspmDatabaseObject),
    "classification_columns": ("/classificationmanagement/columns", DspmClassificationColumn),
    "classification_files": ("/classificationmanagement/files", DspmClassificationFile),
    "data_tags": ("/classificationmanagement/datatags", DspmDataTag),
    "data_tag_categories": ("/classificationmanagement/datatagcategories", DspmCategory),
    "sensitive_data_types": ("/classificationmanagement/sensitivedatatypes", DspmSensitiveDataType),
    "sensitive_data_type_categories": (
        "/classificationmanagement/sensitivedatatypecategories",
        DspmCategory,
    ),
    "sensitivity_levels": (
        "/classificationmanagement/sensitivedatatypes/sensitivitylevels",
        DspmRecord,
    ),
    "sidecar_pools": ("/administration/sidecarpools", DspmSidecarPool),
    "infrastructure_connections": (
        "/administration/infrastructureconnections",
        DspmInfrastructureConnection,
    ),
    "infrastructure_platforms": ("/administration/infrastructureconnections/platforms", DspmRecord),
}
_SCAN_PATH = "/api/v2/dspm/datastores/connected/startscan"


def supported_resource_types() -> tuple[DspmResourceType, ...]:
    return tuple(DspmResourceType(value) for value in _ROUTES)


def _prepare(
    resource_type: DspmResourceType | str,
    filter_expr: str | None,
    sort_by: str | None,
    sort_order: SortOrder | str | None,
    limit: int | None,
    offset: int | None,
) -> tuple[str, type[DspmRecord], dict[str, Any]]:
    resource = _validate_resource_type(resource_type)
    if resource not in _ROUTES:
        raise ValidationError(
            f"No verified public DSPM read contract for {resource}. Supported resource names "
            "are available from DspmResource.supported_resource_types()."
        )
    for name, value in (("limit", limit), ("offset", offset)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ValidationError(f"{name} must be a nonnegative integer.")
    for name, text_value in (("filter_expr", filter_expr), ("sort_by", sort_by)):
        if text_value is not None and not isinstance(text_value, str):
            raise ValidationError(f"{name} must be a string.")
    if sort_order is not None and sort_order not in ("asc", "desc"):
        raise ValidationError("sort_order must be asc or desc.")
    if sort_order is not None and not sort_by:
        raise ValidationError("sort_order requires sort_by.")
    path, model = _ROUTES[resource]
    return (
        "/api/v2/dspm" + path,
        model,
        _build_list_params(filter_expr, sort_by, sort_order, limit, offset),
    )


def _page(body: Any, model: type[DspmRecord], offset: int, limit: int | None) -> Page[DspmRecord]:
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise ValueError("Expected a DSPM data object.")
    data = body["data"]
    rows = data.get("results")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Expected a DSPM results collection.")
    metadata = {key: value for key, value in body.items() if key != "data"}
    metadata["data"] = {key: value for key, value in data.items() if key != "results"}
    return build_page(
        [model.model_validate(row) for row in rows],
        offset=offset,
        limit=limit,
        total=coerce_total(data.get("total")),
        metadata=metadata,
    )


def _scan_request(datastore_id: str) -> dict[str, Any]:
    try:
        request = DspmScanRequest.model_validate({"id": datastore_id})
    except ModelValidationError:
        raise ValidationError("A scan requires one nonempty datastore ID.") from None
    if not request.id.strip():
        raise ValidationError("A scan requires one nonempty datastore ID.")
    return request.model_dump()


def _scan_ack(response: httpx.Response) -> None:
    if response.status_code != 202:
        raise ValueError(
            f"A DSPM scan request is acknowledged with HTTP 202, not {response.status_code}."
        )


class DspmResponses(SyncResource):
    """Typed DSPM inventory pages and scan acknowledgements, with their buffered responses."""

    def list_page(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[DspmRecord]]:
        path, model, params = _prepare(
            resource_type, filter_expr, sort_by, sort_order, limit, offset
        )
        response = self._transport.request("GET", path, params=params or None)
        return ApiResponse(response, lambda raw: _page(raw.json(), model, offset or 0, limit))

    def start_scan(self, datastore_id: str) -> ApiResponse[None]:
        response = self._transport.request(
            "POST", _SCAN_PATH, json=_scan_request(datastore_id), retry_safe=False
        )
        return ApiResponse(response, _scan_ack)


class AsyncDspmResponses(AsyncResource):
    """Typed DSPM inventory pages and scan acknowledgements, with their buffered responses."""

    async def list_page(
        self,
        resource_type: DspmResourceType | str,
        *,
        filter_expr: str | None = None,
        sort_by: str | None = None,
        sort_order: SortOrder | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse[Page[DspmRecord]]:
        path, model, params = _prepare(
            resource_type, filter_expr, sort_by, sort_order, limit, offset
        )
        response = await self._transport.request("GET", path, params=params or None)
        return ApiResponse(response, lambda raw: _page(raw.json(), model, offset or 0, limit))

    async def start_scan(self, datastore_id: str) -> ApiResponse[None]:
        response = await self._transport.request(
            "POST", _SCAN_PATH, json=_scan_request(datastore_id), retry_safe=False
        )
        return ApiResponse(response, _scan_ack)
