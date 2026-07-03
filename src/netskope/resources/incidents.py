"""Incidents resource — view and manage security incidents.

Example::

    for incident in client.incidents.list():
        print(f"{incident.incident_id} — {incident.severity}")

    # Get user confidence index (risk score)
    uci = client.incidents.get_uci("user@example.com")
    print(f"Risk score: {uci.score}")
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime, timedelta
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models.incidents import Anomaly, Incident, IncidentNote, UserConfidenceIndex
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, quote_id, validate_id

_SEARCH_PATH = "/api/v2/events/datasearch/incident"
_UPDATE_PATH = "/api/v2/incidents/update"
_DLP_INCIDENTS_PATH = "/api/v2/incidents/dlpincidents"
_UCI_PATH = "/api/v2/ubadatasvc/user/uci"
_ANOMALIES_PATH = "/api/v2/incidents/users/getanomalies"

_VALID_UPDATE_FIELDS = ("status", "assignee", "severity")
_VALID_SEVERITIES = ("Critical", "High", "Medium", "Low", "Informational")
_UCI_DEFAULT_WINDOW = timedelta(days=7)

# The API rejects note content at 512 characters or more — enforce
# strict-less-than client-side so callers fail fast with a clear message.
_NOTE_CONTENT_LIMIT = 512


def _build_list_params(
    query: str | None,
    fields: builtins.list[str] | None,
    start_time: datetime | int | None,
    end_time: datetime | int | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
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


def _build_uci_payload(username: str, from_time: datetime | int | None) -> dict[str, Any]:
    if from_time is None:
        from_time_ms = int((datetime.now(tz=UTC) - _UCI_DEFAULT_WINDOW).timestamp() * 1000)
    elif isinstance(from_time, datetime):
        from_time_ms = int(from_time.timestamp() * 1000)
    else:
        from_time_ms = from_time
    return {"user": username, "fromTime": from_time_ms}


def _build_anomalies_payload(
    users: builtins.list[str],
    timeframe: int,
    severity: str | builtins.list[str] | None,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> dict[str, Any]:
    if not 1 <= timeframe <= 90:
        raise ValidationError(f"Invalid timeframe {timeframe!r}. Must be between 1 and 90 days.")
    if not 1 <= limit <= 10000:
        raise ValidationError(f"Invalid limit {limit!r}. Must be between 1 and 10000.")
    if sort_order not in ("asc", "desc"):
        raise ValidationError(f"Invalid sort_order {sort_order!r}. Must be 'asc' or 'desc'.")
    payload: dict[str, Any] = {
        "users": users,
        "timeframe": timeframe,
        "limit": limit,
        "offset": offset,
        "sortby": sort_by,
        "sortorder": sort_order,
    }
    if severity is not None:
        severities = [severity] if isinstance(severity, str) else list(severity)
        invalid = [s for s in severities if s not in _VALID_SEVERITIES]
        if invalid:
            raise ValidationError(
                f"Invalid severity value(s): {', '.join(invalid)}. "
                f"Must be one of: {', '.join(_VALID_SEVERITIES)}"
            )
        payload["severity_filter"] = severities
    return payload


def _notes_path(dlp_incident_id: str) -> str:
    return f"{_DLP_INCIDENTS_PATH}/{quote_id(dlp_incident_id)}/notes"


def _validate_note_content(content: str) -> None:
    if len(content) >= _NOTE_CONTENT_LIMIT:
        raise ValidationError(
            f"Note content is {len(content)} characters; it must be under {_NOTE_CONTENT_LIMIT}."
        )


class IncidentsResource(SyncResource):
    """Synchronous interface to the Incidents API."""

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        page_size: int = 100,
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
            params=_build_list_params(query, fields, start_time, end_time),
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
                is converted to epoch milliseconds; an ``int`` is passed
                through unchanged and must already be epoch milliseconds.

        Returns:
            A :class:`~netskope.models.incidents.UserConfidenceIndex`.
        """
        body = self._post(_UCI_PATH, json=_build_uci_payload(username, from_time))
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

        Args:
            users: List of user email addresses.
            timeframe: Number of days to look back (1-90, default 30).
            severity: Severity filter — a single level or a list of levels.
                Valid levels: Critical, High, Medium, Low, Informational.
            limit: Maximum number of results (1-10000, default 100).
            offset: Pagination offset.
            sort_by: Field to sort results by (default ``"time"``).
            sort_order: ``"asc"`` or ``"desc"`` (default ``"desc"``).

        Raises:
            netskope.exceptions.ValidationError: If a parameter is out of range.
        """
        payload = _build_anomalies_payload(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        body = self._post(_ANOMALIES_PATH, json=payload)
        return [Anomaly.model_validate(item) for item in extract_list(body)]

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

    def list(
        self,
        *,
        query: str | None = None,
        fields: builtins.list[str] | None = None,
        start_time: datetime | int | None = None,
        end_time: datetime | int | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Incident]:
        """List incidents with optional JQL filtering."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_SEARCH_PATH,
            params=_build_list_params(query, fields, start_time, end_time),
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

        ``from_time=None`` (default) means "now minus 7 days"; a
        :class:`~datetime.datetime` is converted to epoch milliseconds; an
        ``int`` must already be epoch milliseconds and is passed through.
        """
        body = await self._post(_UCI_PATH, json=_build_uci_payload(username, from_time))
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
        payload = _build_anomalies_payload(
            users, timeframe, severity, limit, offset, sort_by, sort_order
        )
        body = await self._post(_ANOMALIES_PATH, json=payload)
        return [Anomaly.model_validate(item) for item in extract_list(body)]

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
