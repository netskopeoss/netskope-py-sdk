"""Typed incident operations; legacy methods keep their existing signatures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.alerts import DatasearchBucket
from netskope.models.incidents import (
    Anomaly,
    Incident,
    IncidentForensics,
    IncidentNote,
    IncidentNoteCreate,
    IncidentUpdateOutcome,
    IncidentUpdateRequest,
    IncidentUpdateResult,
    UserConfidenceIndex,
)
from netskope.pagination import Page
from netskope.resources._alert_query import (
    _build_aggregate_params,
    _build_page_params,
    _parse_aggregate_page,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._event_response import _parse_page
from netskope.resources._extract import quote_id
from netskope.resources._response_list import parse_response_list
from netskope.resources.incidents import (
    _ANOMALIES_PATH,
    _DLP_INCIDENTS_PATH,
    _SEARCH_PATH,
    _UCI_PATH,
    _UPDATE_PATH,
    _build_anomalies_request,
    _build_uci_payload,
    _notes_path,
)
from netskope.response import ApiResponse

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


def _request(model: type[M], values: dict[str, Any]) -> M:
    try:
        return model.model_validate(values)
    except PydanticValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) or "target" for error in exc.errors())
        raise ValidationError(f"Invalid incident request: {fields}.") from None


def _object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError("Expected an incident response object.")
    for key in ("data", "result"):
        if isinstance(body.get(key), dict):
            return dict(body[key])
    return body


def _uci(body: Any) -> UserConfidenceIndex:
    data = _object(body)
    if isinstance(data.get("data"), list):
        if len(data["data"]) != 1:
            raise ValueError("Expected one user's UCI result.")
        data = _object(data["data"][0])
    # ubadatasvc.yaml:61-69 defines the reply as confidences plus userId. The
    # score/user keys are not in that schema; they are accepted here only so a
    # tenant returning them is not rejected outright, and they reach the caller
    # through the model's extra fields rather than a declared attribute.
    if not any(key in data for key in ("confidences", "score", "user", "userId")):
        raise ValueError("Expected a UCI time series or score result.")
    return UserConfidenceIndex.model_validate(data)


def _forensics(body: Any) -> IncidentForensics:
    data = _object(body)
    reported = data.get("error")
    if isinstance(reported, str) and reported.strip():
        # ims_forensics.yaml:25-36 makes `data` a oneOf[Forensics, Error], and
        # :60-94 shows the Error arm returned on HTTP 200 too. Name the reason
        # rather than reporting an unrecognised envelope.
        raise ResponseValidationError(f"The forensics request failed: {reported}")
    if not any(key in data for key in ("content", "meta", "preview_image")):
        raise ValueError("Expected a DLP forensics result.")
    return IncidentForensics.model_validate(data)


def _note(body: Any) -> IncidentNote:
    data = body if isinstance(body, dict) and "note_id" in body else _object(body)
    if not any(key in data for key in ("note_id", "content")):
        raise ValueError("Expected an incident note.")
    return IncidentNote.model_validate(data)


def _update_result(body: Any) -> IncidentUpdateResult:
    """Decode update acknowledgements; ``ok`` is the flag, ``result`` may be a message."""
    if not isinstance(body, dict):
        raise ValueError("Expected incident update outcomes.")
    raw = body.get("result")
    entries = raw if isinstance(raw, list) else [body]
    if not entries:
        raise ValueError("Expected at least one incident update outcome.")
    outcomes = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Expected an incident update outcome object.")
        ok = entry.get("ok")
        if isinstance(ok, bool) or not isinstance(ok, (int, str)):
            raise ValueError("Incident update outcomes must report an integer ok flag.")
        if isinstance(ok, str) and not ok.isdecimal():
            raise ValueError("Incident update outcomes must report an integer ok flag.")
        outcomes.append(IncidentUpdateOutcome.model_validate(entry))
    return IncidentUpdateResult.model_validate({**body, "outcomes": outcomes})


def _deleted(body: Any) -> None:
    if not isinstance(body, dict):
        raise ValueError("Expected a note deletion acknowledgement.")
    if body.get("success") is False:
        raise ValueError("The note deletion was not acknowledged.")
    if body and body.get("success") is not True and body.get("status") != "success":
        raise ValueError("Expected a note deletion acknowledgement.")


class IncidentResponses(SyncResource):
    """Opt-in original responses for typed, single-request incident operations."""

    def _response(
        self,
        method: str,
        path: str,
        parser: Callable[[Any], T],
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        retry_safe: bool | None = None,
    ) -> ApiResponse[T]:
        """Send one request; only an explicit ``retry_safe=True`` lets a POST replay."""
        raw = self._transport.request(method, path, params=params, json=json, retry_safe=retry_safe)
        return ApiResponse(
            raw, lambda response: parser(response.json() if response.content else {})
        )

    def list_page(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[Incident]]:
        params = _build_page_params(
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            timeout=timeout,
        )
        return self._response(
            "GET",
            _SEARCH_PATH,
            lambda body: _parse_page(body, Incident, offset or 0, limit),
            params=params,
        )

    def aggregate_page(
        self,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        params = _build_aggregate_params(
            group_by,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            limit,
            timeout=timeout,
        )
        return self._response(
            "GET", _SEARCH_PATH, lambda body: _parse_aggregate_page(body, limit), params=params
        )

    def update_one(
        self,
        incident_id: int,
        *,
        field: str,
        new_value: str,
        user: str,
    ) -> ApiResponse[IncidentUpdateResult]:
        request = _request(
            IncidentUpdateRequest,
            {
                "incident_id": incident_id,
                "field": field,
                "new_value": new_value,
                "user": user,
            },
        )
        return self._response(
            "PATCH",
            _UPDATE_PATH,
            _update_result,
            json={"payload": [request.model_dump(exclude_none=True)]},
            retry_safe=False,
        )

    def update_object(
        self,
        object_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> ApiResponse[IncidentUpdateResult]:
        request = _request(
            IncidentUpdateRequest,
            {
                "object_id": object_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "user": user,
            },
        )
        return self._response(
            "PATCH",
            _UPDATE_PATH,
            _update_result,
            json={"payload": [request.model_dump(exclude_none=True)]},
            retry_safe=False,
        )

    def get_forensics(self, dlp_incident_id: str) -> ApiResponse[IncidentForensics]:
        return self._response(
            "GET", f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/forensics", _forensics
        )

    def get_uci(
        self,
        username: str,
        *,
        from_time: datetime | int | None = None,
    ) -> ApiResponse[UserConfidenceIndex]:
        return self._response(
            "POST",
            _UCI_PATH,
            _uci,
            json=_build_uci_payload(username, from_time),
            retry_safe=True,
        )

    def get_anomalies(
        self,
        users: list[str],
        *,
        timeframe: int = 30,
        severity: str | list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "time",
        sort_order: str = "desc",
    ) -> ApiResponse[list[Anomaly]]:
        body, params = _build_anomalies_request(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        return self._response(
            "POST",
            _ANOMALIES_PATH,
            lambda payload: parse_response_list(payload, Anomaly, "results"),
            json=body,
            params=params,
            retry_safe=True,
        )

    def list_notes(self, dlp_incident_id: str) -> ApiResponse[list[IncidentNote]]:
        return self._response(
            "GET",
            _notes_path(dlp_incident_id),
            lambda body: parse_response_list(body, IncidentNote),
        )

    def add_note(self, dlp_incident_id: str, content: str) -> ApiResponse[IncidentNote]:
        request = _request(IncidentNoteCreate, {"content": content})
        return self._response(
            "POST", _notes_path(dlp_incident_id), _note, json=request.model_dump(), retry_safe=False
        )

    def delete_note(self, dlp_incident_id: str, note_id: str) -> ApiResponse[None]:
        return self._response(
            "DELETE",
            f"{_notes_path(dlp_incident_id)}/{quote_id(note_id)}",
            _deleted,
            retry_safe=False,
        )


class AsyncIncidentResponses(AsyncResource):
    """Opt-in original responses for typed, single-request incident operations."""

    async def _response(
        self,
        method: str,
        path: str,
        parser: Callable[[Any], T],
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        retry_safe: bool | None = None,
    ) -> ApiResponse[T]:
        """Send one request; only an explicit ``retry_safe=True`` lets a POST replay."""
        raw = await self._transport.request(
            method, path, params=params, json=json, retry_safe=retry_safe
        )
        return ApiResponse(
            raw, lambda response: parser(response.json() if response.content else {})
        )

    async def list_page(
        self,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[Incident]]:
        params = _build_page_params(
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            offset,
            limit,
            timeout=timeout,
        )
        return await self._response(
            "GET",
            _SEARCH_PATH,
            lambda body: _parse_page(body, Incident, offset or 0, limit),
            params=params,
        )

    async def aggregate_page(
        self,
        *,
        group_by: str | list[str],
        query: str | None = None,
        fields: list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> ApiResponse[Page[DatasearchBucket]]:
        params = _build_aggregate_params(
            group_by,
            query,
            fields,
            start_time,
            end_time,
            order_by,
            descending,
            limit,
            timeout=timeout,
        )
        return await self._response(
            "GET", _SEARCH_PATH, lambda body: _parse_aggregate_page(body, limit), params=params
        )

    async def update_one(
        self,
        incident_id: int,
        *,
        field: str,
        new_value: str,
        user: str,
    ) -> ApiResponse[IncidentUpdateResult]:
        request = _request(
            IncidentUpdateRequest,
            {
                "incident_id": incident_id,
                "field": field,
                "new_value": new_value,
                "user": user,
            },
        )
        return await self._response(
            "PATCH",
            _UPDATE_PATH,
            _update_result,
            json={"payload": [request.model_dump(exclude_none=True)]},
            retry_safe=False,
        )

    async def update_object(
        self,
        object_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> ApiResponse[IncidentUpdateResult]:
        request = _request(
            IncidentUpdateRequest,
            {
                "object_id": object_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "user": user,
            },
        )
        return await self._response(
            "PATCH",
            _UPDATE_PATH,
            _update_result,
            json={"payload": [request.model_dump(exclude_none=True)]},
            retry_safe=False,
        )

    async def get_forensics(self, dlp_incident_id: str) -> ApiResponse[IncidentForensics]:
        return await self._response(
            "GET", f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/forensics", _forensics
        )

    async def get_uci(
        self,
        username: str,
        *,
        from_time: datetime | int | None = None,
    ) -> ApiResponse[UserConfidenceIndex]:
        return await self._response(
            "POST",
            _UCI_PATH,
            _uci,
            json=_build_uci_payload(username, from_time),
            retry_safe=True,
        )

    async def get_anomalies(
        self,
        users: list[str],
        *,
        timeframe: int = 30,
        severity: str | list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "time",
        sort_order: str = "desc",
    ) -> ApiResponse[list[Anomaly]]:
        body, params = _build_anomalies_request(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        return await self._response(
            "POST",
            _ANOMALIES_PATH,
            lambda payload: parse_response_list(payload, Anomaly, "results"),
            json=body,
            params=params,
            retry_safe=True,
        )

    async def list_notes(self, dlp_incident_id: str) -> ApiResponse[list[IncidentNote]]:
        return await self._response(
            "GET",
            _notes_path(dlp_incident_id),
            lambda body: parse_response_list(body, IncidentNote),
        )

    async def add_note(self, dlp_incident_id: str, content: str) -> ApiResponse[IncidentNote]:
        request = _request(IncidentNoteCreate, {"content": content})
        return await self._response(
            "POST", _notes_path(dlp_incident_id), _note, json=request.model_dump(), retry_safe=False
        )

    async def delete_note(self, dlp_incident_id: str, note_id: str) -> ApiResponse[None]:
        return await self._response(
            "DELETE",
            f"{_notes_path(dlp_incident_id)}/{quote_id(note_id)}",
            _deleted,
            retry_safe=False,
        )
