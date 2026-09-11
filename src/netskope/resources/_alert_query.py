"""Shared alert request construction and response decoding."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from netskope._pagination import _make_page
from netskope.datasearch import DATASEARCH_PAGE_CAP, DatasearchWindow
from netskope.exceptions import ValidationError
from netskope.models.alerts import Alert, DatasearchBucket
from netskope.pagination import Page

_PATH = "/api/v2/events/datasearch/alert"
_HEX_ID_RE = re.compile(r"[a-fA-F0-9]+")


class _AlertQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str | None = None
    fields: list[str] | None = None
    start_time: int | None = None
    end_time: int | None = None
    group_by: str | list[str] | None = None
    order_by: str | None = None
    descending: bool | None = None
    offset: int | None = Field(None, ge=0)
    limit: int | None = Field(None, gt=0, le=DATASEARCH_PAGE_CAP)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _epoch(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Datetime bounds must include a timezone.")
            return int(value.timestamp())
        return value

    @model_validator(mode="after")
    def _ordered_bounds(self) -> _AlertQuery:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError("end_time must not precede start_time.")
        return self


def _build_params(
    query: str | None = None,
    fields: list[str] | None = None,
    start_time: datetime | int | None = None,
    end_time: datetime | int | None = None,
    group_by: str | list[str] | None = None,
    order_by: str | None = None,
    descending: bool | None = True,
) -> dict[str, Any]:
    """Preserve legacy parameter behavior, including its default DESC direction."""
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if fields:
        params["fields"] = ",".join(fields)
    for key, bound in (("starttime", start_time), ("endtime", end_time)):
        if bound is not None:
            params[key] = int(bound.timestamp()) if isinstance(bound, datetime) else bound
    if group_by:
        params["groupbys"] = group_by if isinstance(group_by, str) else ",".join(group_by)
    if order_by:
        direction = "" if descending is None else (" DESC" if descending else " ASC")
        params["sortby"] = f"{order_by}{direction}"
    return params


def _build_page_params(
    query: str | None,
    fields: list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    order_by: str | None,
    descending: bool | None,
    offset: int | None,
    limit: int | None,
    *,
    group_by: str | list[str] | None = None,
) -> dict[str, Any]:
    try:
        request = _AlertQuery.model_validate(
            {
                "query": query,
                "fields": fields,
                "start_time": start_time,
                "end_time": end_time,
                "group_by": group_by,
                "order_by": order_by,
                "descending": descending,
                "offset": offset,
                "limit": limit,
            }
        )
    except PydanticValidationError as exc:
        locations = ", ".join(
            ".".join(map(str, error["loc"])) or "time bounds" for error in exc.errors()
        )
        raise ValidationError(f"Invalid datasearch request parameters: {locations}.") from None
    params = _build_params(
        request.query,
        request.fields,
        request.start_time,
        request.end_time,
        request.group_by,
        request.order_by,
        request.descending,
    )
    if "sortby" in params:
        # search_alert.yaml defines orderbys. Legacy list() keeps its existing
        # sortby wire contract through _build_params directly.
        params["orderbys"] = params.pop("sortby")
    if request.offset is not None:
        params["offset"] = request.offset
    if request.limit is not None:
        params["limit"] = request.limit
    return params


def _build_aggregate_params(
    group_by: str | list[str],
    query: str | None,
    fields: list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    order_by: str | None,
    descending: bool | None,
    limit: int | None,
) -> dict[str, Any]:
    params = _build_page_params(
        query, fields, start_time, end_time, order_by, descending, None, limit, group_by=group_by
    )
    if "groupbys" not in params:
        raise ValidationError("group_by must select at least one grouping field.")
    return params


def _build_scan_params(
    window: DatasearchWindow,
    query: str | None,
    fields: list[str] | None,
    order_by: str | None,
    descending: bool | None,
) -> dict[str, Any]:
    if not isinstance(window, DatasearchWindow):
        raise ValidationError("window must be a DatasearchWindow with explicit epoch bounds.")
    params = _build_page_params(
        query, fields, window.start_time, window.end_time, order_by, descending, None, None
    )
    if "fields" in params:
        names = params["fields"].split(",")
        if "_id" not in names:
            params["fields"] = ",".join([*names, "_id"])
    return params


def _validate_alert_id(alert_id: str) -> None:
    if not isinstance(alert_id, str) or _HEX_ID_RE.fullmatch(alert_id) is None:
        raise ValidationError("Invalid alert_id format. Expected a hex string.")


def _extract_alerts(body: Any) -> list[dict[str, Any]]:
    """Decode known envelopes without turning malformed responses into empty pages."""
    if not isinstance(body, dict):
        raise ValueError("Expected an alert response envelope.")
    for key in ("result", "data"):
        if key not in body:
            continue
        rows = body[key]
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Expected a list of datasearch records.")
        return cast(list[dict[str, Any]], rows)
    raise ValueError("The response has no datasearch records envelope.")


def _metadata(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in ("result", "data")}


def _parse_alerts_page(body: Any, offset: int, limit: int | None) -> Page[Alert]:
    items = [Alert.model_validate(row) for row in _extract_alerts(body)]
    page = _make_page(items, _metadata(body), offset, limit)
    if page.total is None and limit is not None and len(items) < limit:
        page.has_more = False
    return page


def _parse_aggregate_page(body: Any, limit: int | None) -> Page[DatasearchBucket]:
    items = [DatasearchBucket.model_validate(row) for row in _extract_alerts(body)]
    # No current endpoint contract establishes whether an envelope total counts
    # groups or source events, so preserve it without claiming a group total.
    return Page(items=items, total=None, offset=0, limit=limit, metadata=_metadata(body))
