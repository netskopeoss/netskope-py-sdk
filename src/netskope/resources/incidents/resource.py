"""Incidents resource — view and manage security incidents.

Example::

    for incident in client.incidents.list():
        print(f"{incident.incident_id} — {incident.severity}")

    # Get user confidence index (risk score). The response is a time series
    # of confidence points, not a single score; the last point is current.
    uci = client.incidents.get_uci("user@example.com")
    latest = (uci.confidences or [])[-1:]
    for point in latest:
        print(f"Risk score: {point.confidence_score}")
"""

from __future__ import annotations

import builtins
import functools
from datetime import datetime
from typing import Any

from netskope.core.ids import extract_item, extract_list, quote_id, validate_id
from netskope.core.pagination import AsyncPaginatedResponse, Page, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.datasearch import DATASEARCH_TIMEOUT_DEFAULT
from netskope.exceptions import ValidationError
from netskope.models.incidents import (
    Anomaly,
    Incident,
    IncidentNote,
    IncidentUpdateResult,
    UserConfidenceIndex,
)
from netskope.resources.incidents.decoder import AsyncIncidentResponses, IncidentResponses
from netskope.resources.incidents.paths import (
    _ANOMALIES_PATH,
    _DLP_INCIDENTS_PATH,
    _SEARCH_PATH,
    _UCI_PATH,
    _UPDATE_PATH,
    _build_anomalies_request,
    _build_uci_payload,
    _notes_path,
)
from netskope.resources.shared.datasearch_query import _validate_timeout

_VALID_UPDATE_FIELDS = ("status", "assignee", "severity")

# The API rejects note content at 512 characters or more — enforce
# strict-less-than client-side so callers fail fast with a clear message.
_NOTE_CONTENT_LIMIT = 512


def _build_list_params(
    query: str | None,
    fields: builtins.list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
    timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
) -> dict[str, Any]:
    # search_incident.yaml:458-465 marks the query timeout required with a
    # declared default of 180, so it is always sent.
    params: dict[str, Any] = {"timeout": _validate_timeout(timeout)}
    if query:
        params["query"] = query
    if fields:
        params["fields"] = ",".join(fields)
    if start_time is not None:
        params["starttime"] = (
            int(start_time.timestamp()) if isinstance(start_time, datetime) else start_time
        )
    if end_time is not None:
        params["endtime"] = (
            int(end_time.timestamp()) if isinstance(end_time, datetime) else end_time
        )
    return params


def _build_update_payload(
    incident_id: str,
    field: str,
    old_value: str,
    new_value: str,
    user: str,
) -> dict[str, Any]:
    validate_id(incident_id, "incident_id")
    if field not in _VALID_UPDATE_FIELDS:
        raise ValidationError(
            f"Invalid field {field!r}. Must be one of: {', '.join(_VALID_UPDATE_FIELDS)}"
        )
    return {
        "payload": [
            {
                "object_id": incident_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "user": user,
            }
        ]
    }


def _validate_note_content(content: str) -> None:
    if len(content) >= _NOTE_CONTENT_LIMIT:
        raise ValidationError(
            f"Note content is {len(content)} characters; it must be under {_NOTE_CONTENT_LIMIT}."
        )


class IncidentsResource(SyncResource):
    """Synchronous interface to the Incidents API."""

    @functools.cached_property
    def with_response(self) -> IncidentResponses:

        return IncidentResponses(self._transport)

    def list_page(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[Incident]:
        """Fetch and validate exactly one incident event page."""
        return self.with_response.list_page(
            query=query,
            fields=fields,
            start_time=start_time,
            end_time=end_time,
            order_by=order_by,
            descending=descending,
            offset=offset,
            limit=limit,
            timeout=timeout,
        ).parse()

    def update_one(
        self,
        incident_id: int,
        *,
        field: str,
        new_value: str,
        user: str,
    ) -> IncidentUpdateResult:
        """Update by numeric incident ID; acceptance does not prove a row changed."""
        return self.with_response.update_one(
            incident_id,
            field=field,
            new_value=new_value,
            user=user,
        ).parse()

    def update_object(
        self,
        object_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> IncidentUpdateResult:
        """Update matching incidents attached to one object. This can change many rows."""
        return self.with_response.update_object(
            object_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            user=user,
        ).parse()

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> SyncPaginatedResponse[Incident]:
        """List incidents with optional JQL filtering.

        Args:
            query: JQL filter expression.
            fields: Specific fields to return.
            start_time: Start of time range.
            end_time: End of time range.
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_SEARCH_PATH,
            params=_build_list_params(query, fields, start_time, end_time, timeout),
            model=Incident,
            page_size=page_size,
            extract=extract_list,
        )

    def update(
        self,
        incident_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> dict[str, Any]:
        """Update an incident field (with concurrency guard).

        Args:
            incident_id: The incident identifier.
            field: Field to update — one of ``"status"``, ``"assignee"``,
                or ``"severity"``.
            old_value: Expected current value (optimistic lock).
            new_value: Desired new value.
            user: Email of the user making the change.

        Raises:
            netskope.exceptions.ValidationError: If *field* is not a
                supported update field.
        """
        payload = _build_update_payload(incident_id, field, old_value, new_value, user)
        return self._patch(_UPDATE_PATH, json=payload)

    def get_forensics(self, dlp_incident_id: str) -> dict[str, Any]:
        """Get DLP forensics data for an incident.

        Args:
            dlp_incident_id: The DLP incident identifier (the
                ``dlp_incident_id`` field, not the regular incident id).
        """
        return self._get(f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/forensics")

    def get_uci(
        self,
        username: str,
        *,
        from_time: datetime | int | None = None,
    ) -> UserConfidenceIndex:
        """Get the User Confidence Index (risk score) for a user.

        Args:
            username: The user's email address.
            from_time: Start of the scoring window.  ``None`` (default)
                means "now minus 7 days".  A :class:`~datetime.datetime`
                must carry a timezone and is converted to epoch
                milliseconds; an ``int`` is passed through unchanged and
                must already be epoch milliseconds (``0`` is valid).

        Returns:
            A :class:`~netskope.models.incidents.UserConfidenceIndex`.

        Raises:
            netskope.exceptions.ValidationError: If *username* is blank or
                *from_time* is a naive datetime.
        """
        body = self._post(_UCI_PATH, json=_build_uci_payload(username, from_time), retry_safe=True)
        data = body.get("data", body)
        if isinstance(data, list) and data:
            data = data[0]
        return UserConfidenceIndex.model_validate(data)

    def get_anomalies(
        self,
        users: builtins.list[str],
        *,
        timeframe: int = 30,
        severity: str | builtins.list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "time",
        sort_order: str = "desc",
    ) -> builtins.list[Anomaly]:
        """Get UBA anomalies for the specified users.

        The request body carries ``users`` and ``timeframe``; paging and sorting
        travel as query parameters.

        Args:
            users: List of user email addresses.
            timeframe: Number of days to look back (at least 1, default 30).
                The endpoint declares no upper bound.
            severity: Unsupported — the endpoint has no server-side severity
                filter, so a value here is rejected instead of silently dropped.
            limit: Maximum number of results (1-10000, default 100).
            offset: Pagination offset.
            sort_by: Field to sort results by (default ``"time"``).
            sort_order: ``"asc"`` or ``"desc"``. The SDK default is
                ``"desc"`` (newest first); the endpoint's own default is
                ``"asc"`` (uba.yaml:2205-2216), so leaving this unset still
                sends an explicit ``sortorder``.

        Raises:
            netskope.exceptions.ValidationError: If *severity* is supplied or a
                parameter is out of range.
        """
        payload, params = _build_anomalies_request(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        body = self._post(_ANOMALIES_PATH, json=payload, retry_safe=True, **params)
        # uba.yaml:926-937 requires both `results` and `totalCount`.
        return [Anomaly.model_validate(item) for item in extract_list(body, "results")]

    def list_notes(self, dlp_incident_id: str) -> builtins.list[IncidentNote]:
        """List notes attached to a DLP incident.

        Args:
            dlp_incident_id: The DLP incident identifier.

        Returns:
            A list of :class:`~netskope.models.incidents.IncidentNote`.
        """
        body = self._get(_notes_path(dlp_incident_id))
        return [IncidentNote.model_validate(item) for item in extract_list(body)]

    def add_note(self, dlp_incident_id: str, content: str) -> IncidentNote:
        """Add a note to a DLP incident.

        Each incident can hold at most 25 notes; the API returns 409 when
        that limit is reached.

        Args:
            dlp_incident_id: The DLP incident identifier.
            content: Note text.  Must be under 512 characters.

        Raises:
            netskope.exceptions.ValidationError: If *content* is 512
                characters or longer.
        """
        _validate_note_content(content)
        body = self._post(_notes_path(dlp_incident_id), json={"content": content})
        return IncidentNote.model_validate(extract_item(body))

    def delete_note(self, dlp_incident_id: str, note_id: str) -> None:
        """Delete a note from a DLP incident.  Irreversible.

        Args:
            dlp_incident_id: The DLP incident identifier.
            note_id: The identifier of the note to delete.
        """
        self._delete(f"{_notes_path(dlp_incident_id)}/{quote_id(note_id)}")


class AsyncIncidentsResource(AsyncResource):
    """Asynchronous interface to the Incidents API."""

    @functools.cached_property
    def with_response(self) -> AsyncIncidentResponses:

        return AsyncIncidentResponses(self._transport)

    async def list_page(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        order_by: str | None = None,
        descending: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> Page[Incident]:
        """Fetch and validate exactly one incident event page."""
        return (
            await self.with_response.list_page(
                query=query,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                order_by=order_by,
                descending=descending,
                offset=offset,
                limit=limit,
                timeout=timeout,
            )
        ).parse()

    async def update_one(
        self,
        incident_id: int,
        *,
        field: str,
        new_value: str,
        user: str,
    ) -> IncidentUpdateResult:
        """Update by numeric incident ID; acceptance does not prove a row changed."""
        return (
            await self.with_response.update_one(
                incident_id,
                field=field,
                new_value=new_value,
                user=user,
            )
        ).parse()

    async def update_object(
        self,
        object_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> IncidentUpdateResult:
        """Update matching incidents attached to one object. This can change many rows."""
        return (
            await self.with_response.update_object(
                object_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
                user=user,
            )
        ).parse()

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        page_size: int = 100,
        timeout: int | None = DATASEARCH_TIMEOUT_DEFAULT,
    ) -> AsyncPaginatedResponse[Incident]:
        """List incidents with optional JQL filtering."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_SEARCH_PATH,
            params=_build_list_params(query, fields, start_time, end_time, timeout),
            model=Incident,
            page_size=page_size,
            extract=extract_list,
        )

    async def update(
        self,
        incident_id: str,
        *,
        field: str,
        old_value: str,
        new_value: str,
        user: str,
    ) -> dict[str, Any]:
        """Update an incident field (with concurrency guard).

        See :meth:`IncidentsResource.update`.
        """
        payload = _build_update_payload(incident_id, field, old_value, new_value, user)
        return await self._patch(_UPDATE_PATH, json=payload)

    async def get_forensics(self, dlp_incident_id: str) -> dict[str, Any]:
        """Get DLP forensics data."""
        return await self._get(f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/forensics")

    async def get_uci(
        self,
        username: str,
        *,
        from_time: datetime | int | None = None,
    ) -> UserConfidenceIndex:
        """Get the User Confidence Index (risk score) for a user.

        See :meth:`IncidentsResource.get_uci` — a blank username or a naive
        *from_time* is rejected before the request is sent.
        """
        body = await self._post(
            _UCI_PATH, json=_build_uci_payload(username, from_time), retry_safe=True
        )
        data = body.get("data", body)
        if isinstance(data, list) and data:
            data = data[0]
        return UserConfidenceIndex.model_validate(data)

    async def get_anomalies(
        self,
        users: builtins.list[str],
        *,
        timeframe: int = 30,
        severity: str | builtins.list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "time",
        sort_order: str = "desc",
    ) -> builtins.list[Anomaly]:
        """Get UBA anomalies for users.

        See :meth:`IncidentsResource.get_anomalies`.
        """
        payload, params = _build_anomalies_request(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        body = await self._post(_ANOMALIES_PATH, json=payload, retry_safe=True, **params)
        # uba.yaml:926-937 requires both `results` and `totalCount`.
        return [Anomaly.model_validate(item) for item in extract_list(body, "results")]

    async def list_notes(self, dlp_incident_id: str) -> builtins.list[IncidentNote]:
        """List notes attached to a DLP incident."""
        body = await self._get(_notes_path(dlp_incident_id))
        return [IncidentNote.model_validate(item) for item in extract_list(body)]

    async def add_note(self, dlp_incident_id: str, content: str) -> IncidentNote:
        """Add a note to a DLP incident.  Content must be under 512 characters."""
        _validate_note_content(content)
        body = await self._post(_notes_path(dlp_incident_id), json={"content": content})
        return IncidentNote.model_validate(extract_item(body))

    async def delete_note(self, dlp_incident_id: str, note_id: str) -> None:
        """Delete a note from a DLP incident.  Irreversible."""
        await self._delete(f"{_notes_path(dlp_incident_id)}/{quote_id(note_id)}")
