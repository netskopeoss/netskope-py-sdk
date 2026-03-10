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
import re
from datetime import datetime
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.incidents import Anomaly, Incident, UserConfidenceIndex
from netskope.resources._base import AsyncResource, SyncResource

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

_SEARCH_PATH = "/api/v2/events/datasearch/incident"
_UPDATE_PATH = "/api/v2/incidents/update"
_FORENSICS_PATH = "/api/v2/incidents/dlpincidents"
_UCI_PATH = "/api/v2/ubadatasvc/user/uci"
_ANOMALIES_PATH = "/api/v2/incidents/users/getanomalies"


def _extract(body: dict[str, Any]) -> list[dict[str, Any]]:
    result = body.get("result", [])
    if isinstance(result, list):
        return result
    data = body.get("data", [])
    if isinstance(data, list):
        return data
    return []


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
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_SEARCH_PATH,
            params=params,
            model=Incident,
            page_size=page_size,
            extract=_extract,
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
            field: Field to update (e.g. ``"status"``, ``"assignee"``).
            old_value: Expected current value (optimistic lock).
            new_value: Desired new value.
            user: Email of the user making the change.
        """
        if not _SAFE_ID_RE.match(incident_id):
            from netskope.exceptions import ValidationError

            raise ValidationError(f"Invalid incident_id format: {incident_id!r}")
        payload = {
            "incident_id": incident_id,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "user": user,
        }
        return self._patch(_UPDATE_PATH, json=payload)

    def get_forensics(self, dlp_incident_id: str) -> dict[str, Any]:
        """Get DLP forensics data for an incident.

        Args:
            dlp_incident_id: The DLP incident identifier.
        """
        if not _SAFE_ID_RE.match(dlp_incident_id):
            from netskope.exceptions import ValidationError

            raise ValidationError(f"Invalid dlp_incident_id format: {dlp_incident_id!r}")
        return self._get(f"{_FORENSICS_PATH}/{dlp_incident_id}/forensics")

    def get_uci(self, username: str) -> UserConfidenceIndex:
        """Get the User Confidence Index (risk score) for a user.

        Args:
            username: The user's email address.

        Returns:
            A :class:`~netskope.models.incidents.UserConfidenceIndex`.
        """
        body = self._post(_UCI_PATH, json={"username": username})
        data = body.get("data", body)
        if isinstance(data, list) and data:
            data = data[0]
        return UserConfidenceIndex.model_validate(data)

    def get_anomalies(
        self,
        users: builtins.list[str],
        *,
        timeframe: int | None = None,
        severity: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[Anomaly]:
        """Get UBA anomalies for the specified users.

        Args:
            users: List of user email addresses.
            timeframe: Number of days to look back.
            severity: Filter by severity level.
            limit: Maximum number of results.
        """
        payload: dict[str, Any] = {"users": users}
        if timeframe is not None:
            payload["timeframe"] = timeframe
        if severity is not None:
            payload["severity"] = severity
        if limit is not None:
            payload["limit"] = limit
        body = self._post(_ANOMALIES_PATH, json=payload)
        items = body.get("data", [])
        if not isinstance(items, list):
            items = []
        return [Anomaly.model_validate(item) for item in items]


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
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_SEARCH_PATH,
            params=params,
            model=Incident,
            page_size=page_size,
            extract=_extract,
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
        """Update an incident field."""
        if not _SAFE_ID_RE.match(incident_id):
            from netskope.exceptions import ValidationError

            raise ValidationError(f"Invalid incident_id format: {incident_id!r}")
        payload = {
            "incident_id": incident_id,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "user": user,
        }
        return await self._patch(_UPDATE_PATH, json=payload)

    async def get_forensics(self, dlp_incident_id: str) -> dict[str, Any]:
        """Get DLP forensics data."""
        if not _SAFE_ID_RE.match(dlp_incident_id):
            from netskope.exceptions import ValidationError

            raise ValidationError(f"Invalid dlp_incident_id format: {dlp_incident_id!r}")
        return await self._get(f"{_FORENSICS_PATH}/{dlp_incident_id}/forensics")

    async def get_uci(self, username: str) -> UserConfidenceIndex:
        """Get User Confidence Index."""
        body = await self._post(_UCI_PATH, json={"username": username})
        data = body.get("data", body)
        if isinstance(data, list) and data:
            data = data[0]
        return UserConfidenceIndex.model_validate(data)

    async def get_anomalies(
        self,
        users: builtins.list[str],
        *,
        timeframe: int | None = None,
        severity: str | None = None,
        limit: int | None = None,
    ) -> builtins.list[Anomaly]:
        """Get UBA anomalies for users."""
        payload: dict[str, Any] = {"users": users}
        if timeframe is not None:
            payload["timeframe"] = timeframe
        if severity is not None:
            payload["severity"] = severity
        if limit is not None:
            payload["limit"] = limit
        body = await self._post(_ANOMALIES_PATH, json=payload)
        items = body.get("data", [])
        if not isinstance(items, list):
            items = []
        return [Anomaly.model_validate(item) for item in items]
