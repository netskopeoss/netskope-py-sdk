"""Publisher upgrade profiles resource — schedule publisher software upgrades.

Example::

    for profile in client.npa.upgrade_profiles.list():
        print(f"{profile.name} — {profile.release_type} ({profile.frequency})")

    profile = client.npa.upgrade_profiles.create(
        "weekly-latest",
        docker_tag="8690",
        frequency="0 2 * * SUN",
        timezone="US/Pacific",
        release_type="Latest",
    )
    client.npa.upgrade_profiles.assign(profile.external_id, [10, 20])
"""

from __future__ import annotations

import builtins
from functools import cached_property
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models._npa_requests import request_payload
from netskope.models.infrastructure import (
    PUBLISHER_UPGRADE_TIMEZONES,
    PublisherUpgradeProfile,
    ReleaseType,
    UpgradeProfileAssignment,
    UpgradeProfileCreate,
    UpgradeProfileUpdate,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, id_strings, validate_id
from netskope.resources._npa_response import parse_item
from netskope.resources._response_list import parse_response_list
from netskope.response import ApiResponse

_PATH = "/api/v2/infrastructure/publisherupgradeprofiles"

# Literal sub-path — must never be built via the /{id} route.
_BULK_PATH = f"{_PATH}/bulk"

_VALID_RELEASE_TYPES = frozenset(member.value for member in ReleaseType)
_VALID_TIMEZONES = frozenset(PUBLISHER_UPGRADE_TIMEZONES)


def _validate_release_type(release_type: str) -> str:
    if release_type not in _VALID_RELEASE_TYPES:
        raise ValidationError(
            f"Invalid release_type {release_type!r}. "
            f"Must be one of: {', '.join(sorted(_VALID_RELEASE_TYPES))}"
        )
    return str(release_type)


def _validate_timezone(timezone: str) -> str:
    """Reject a zone name the gateway's closed enum does not carry.

    ``publisher_upgrade_profile_post_request.timezone``
    (npa_upgrade_profiles.yaml:428-497) and the PUT request (:573-650) both
    enumerate the same 69 zone names, so anything else is a round trip the API
    can only reject.
    """
    if timezone not in _VALID_TIMEZONES:
        raise ValidationError(
            f"Invalid timezone {timezone!r}. Must be one of the "
            f"{len(PUBLISHER_UPGRADE_TIMEZONES)} zones the API accepts; see "
            "netskope.models.infrastructure.PUBLISHER_UPGRADE_TIMEZONES."
        )
    return str(timezone)


def _build_create_payload(
    name: str,
    docker_tag: str,
    frequency: str,
    timezone: str,
    release_type: str,
    enabled: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "enabled": enabled,
        "docker_tag": docker_tag,
        "frequency": frequency,
        "timezone": _validate_timezone(timezone),
        "release_type": _validate_release_type(release_type),
    }


def _build_update_payload(
    profile_id: int,
    current: PublisherUpgradeProfile,
    name: str | None,
    enabled: bool | None,
    docker_tag: str | None,
    frequency: str | None,
    timezone: str | None,
    release_type: str | None,
) -> dict[str, Any]:
    """Merge overrides into the current profile for a full-body PUT.

    The gateway spec requires every field (``id``, ``name``, ``enabled``,
    ``docker_tag``, ``frequency``, ``timezone``, ``release_type``) on update,
    so unspecified fields are preserved from the current profile.
    """
    return {
        "id": profile_id,
        "name": name if name is not None else current.name,
        "enabled": enabled if enabled is not None else current.enabled,
        "docker_tag": docker_tag if docker_tag is not None else current.docker_tag,
        "frequency": frequency if frequency is not None else current.frequency,
        "timezone": (_validate_timezone(timezone) if timezone is not None else current.timezone),
        "release_type": (
            _validate_release_type(release_type)
            if release_type is not None
            else current.release_type
        ),
    }


def _build_assign_payload(profile_id: int, publisher_ids: builtins.list[int]) -> dict[str, Any]:
    # The bulk endpoint requires the profile external_id and publisher ids
    # as *strings* (per the gateway spec and the API's actual behavior).
    return {
        "publishers": {
            "apply": {"publisher_upgrade_profiles_id": validate_id(profile_id, "profile_id")},
            "id": id_strings(publisher_ids, "publisher_ids"),
        }
    }


class UpgradeProfileResponses(SyncResource):
    """Completed responses for publisher upgrade-profile queries."""

    def get(self, profile_id: int) -> ApiResponse[PublisherUpgradeProfile]:
        """Fetch one upgrade profile by id; parses to :class:`PublisherUpgradeProfile`."""
        response = self._transport.request("GET", f"{_PATH}/{validate_id(profile_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    def create_request(self, request: UpgradeProfileCreate) -> ApiResponse[PublisherUpgradeProfile]:
        """Create an upgrade profile from a validated request model.

        Returns the created :class:`PublisherUpgradeProfile` with its response envelope.
        """
        payload = request_payload(request, UpgradeProfileCreate)
        response = self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    def update_request(
        self, profile_id: int, request: UpgradeProfileUpdate
    ) -> ApiResponse[PublisherUpgradeProfile]:
        """Replace an upgrade profile; the request id must match *profile_id*.

        Returns the updated :class:`PublisherUpgradeProfile` with its response envelope.
        """
        payload = request_payload(request, UpgradeProfileUpdate)
        if request.id != profile_id:
            raise ValidationError("The profile request id must match profile_id.")
        response = self._transport.request(
            "PUT", f"{_PATH}/{validate_id(profile_id)}", json=payload
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    def assign(
        self, profile_id: int, publisher_ids: builtins.list[int]
    ) -> ApiResponse[UpgradeProfileAssignment]:
        """Assign publishers to one upgrade profile through the bulk endpoint.

        Returns the :class:`UpgradeProfileAssignment` acknowledgement.
        """
        payload = _build_assign_payload(profile_id, publisher_ids)
        response = self._transport.request("PUT", _BULK_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), UpgradeProfileAssignment))

    def list(self) -> ApiResponse[builtins.list[PublisherUpgradeProfile]]:
        """List upgrade profiles with access to their response envelope."""
        response = self._transport.request("GET", _PATH)
        return ApiResponse(
            response,
            lambda raw: parse_response_list(
                raw.json(), PublisherUpgradeProfile, "upgrade_profiles"
            ),
        )


class AsyncUpgradeProfileResponses(AsyncResource):
    """Completed responses for asynchronous upgrade-profile queries."""

    async def get(self, profile_id: int) -> ApiResponse[PublisherUpgradeProfile]:
        """Fetch one upgrade profile by id; parses to :class:`PublisherUpgradeProfile`."""
        response = await self._transport.request("GET", f"{_PATH}/{validate_id(profile_id)}")
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    async def create_request(
        self, request: UpgradeProfileCreate
    ) -> ApiResponse[PublisherUpgradeProfile]:
        """Create an upgrade profile from a validated request model.

        Returns the created :class:`PublisherUpgradeProfile` with its response envelope.
        """
        payload = request_payload(request, UpgradeProfileCreate)
        response = await self._transport.request("POST", _PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    async def update_request(
        self, profile_id: int, request: UpgradeProfileUpdate
    ) -> ApiResponse[PublisherUpgradeProfile]:
        """Replace an upgrade profile; the request id must match *profile_id*.

        Returns the updated :class:`PublisherUpgradeProfile` with its response envelope.
        """
        payload = request_payload(request, UpgradeProfileUpdate)
        if request.id != profile_id:
            raise ValidationError("The profile request id must match profile_id.")
        response = await self._transport.request(
            "PUT", f"{_PATH}/{validate_id(profile_id)}", json=payload
        )
        return ApiResponse(response, lambda raw: parse_item(raw.json(), PublisherUpgradeProfile))

    async def assign(
        self, profile_id: int, publisher_ids: builtins.list[int]
    ) -> ApiResponse[UpgradeProfileAssignment]:
        """Assign publishers to one upgrade profile through the bulk endpoint.

        Returns the :class:`UpgradeProfileAssignment` acknowledgement.
        """
        payload = _build_assign_payload(profile_id, publisher_ids)
        response = await self._transport.request("PUT", _BULK_PATH, json=payload)
        return ApiResponse(response, lambda raw: parse_item(raw.json(), UpgradeProfileAssignment))

    async def list(self) -> ApiResponse[builtins.list[PublisherUpgradeProfile]]:
        """List upgrade profiles with access to their response envelope."""
        response = await self._transport.request("GET", _PATH)
        return ApiResponse(
            response,
            lambda raw: parse_response_list(
                raw.json(), PublisherUpgradeProfile, "upgrade_profiles"
            ),
        )


class UpgradeProfilesResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/publisherupgradeprofiles``."""

    @cached_property
    def with_response(self) -> UpgradeProfileResponses:
        """Inspect a query's completed response and its typed result."""
        return UpgradeProfileResponses(self._transport)

    def list(self) -> builtins.list[PublisherUpgradeProfile]:
        """List all publisher upgrade profiles.

        Returns:
            A list of
            :class:`~netskope.models.infrastructure.PublisherUpgradeProfile`.
        """
        return self.with_response.list().parse()

    def get(self, profile_id: int) -> PublisherUpgradeProfile:
        """Get an upgrade profile by ID.

        Args:
            profile_id: The profile identifier (the profile's ``external_id``).
        """
        body = self._get(f"{_PATH}/{profile_id}")
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    def create(
        self,
        name: str,
        *,
        docker_tag: str,
        frequency: str,
        timezone: str,
        release_type: str,
        enabled: bool = True,
    ) -> PublisherUpgradeProfile:
        """Create a publisher upgrade profile.

        Args:
            name: Human-readable profile name.
            docker_tag: Docker tag of the release to install (see
                ``client.publishers.list_releases()``).
            frequency: Upgrade schedule as a cron expression, e.g.
                ``"0 2 * * SUN"``.
            timezone: Timezone the schedule triggers in, e.g.
                ``"US/Pacific"``.  The API accepts a closed set of zone names;
                see
                :data:`~netskope.models.infrastructure.PUBLISHER_UPGRADE_TIMEZONES`.
            release_type: Release channel — one of
                :class:`~netskope.models.infrastructure.ReleaseType`
                (``Beta``, ``Latest``, ``Latest-1``, ``Latest-2``).
            enabled: Whether the profile is active (default True).

        Raises:
            netskope.exceptions.ValidationError: If *release_type* or
                *timezone* is not a supported value.
        """
        payload = _build_create_payload(
            name, docker_tag, frequency, timezone, release_type, enabled
        )
        body = self._post(_PATH, json=payload)
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    def update(
        self,
        profile_id: int,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        docker_tag: str | None = None,
        frequency: str | None = None,
        timezone: str | None = None,
        release_type: str | None = None,
    ) -> PublisherUpgradeProfile:
        """Update an upgrade profile.

        The API requires the full profile on PUT, so the current profile is
        fetched first and unspecified fields are preserved.

        Args:
            profile_id: The profile identifier (``external_id``).
            name: New profile name.
            enabled: Enable or disable the profile.
            docker_tag: New docker tag.
            frequency: New cron schedule.
            timezone: New schedule timezone, from
                :data:`~netskope.models.infrastructure.PUBLISHER_UPGRADE_TIMEZONES`.
            release_type: New release channel (see
                :class:`~netskope.models.infrastructure.ReleaseType`).

        Raises:
            netskope.exceptions.ValidationError: If *release_type* is not
                a supported value.
        """
        if release_type is not None:
            _validate_release_type(release_type)
        current = self.get(profile_id)
        payload = _build_update_payload(
            profile_id, current, name, enabled, docker_tag, frequency, timezone, release_type
        )
        body = self._put(f"{_PATH}/{profile_id}", json=payload)
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    def delete(self, profile_id: int) -> None:
        """Delete an upgrade profile.

        Args:
            profile_id: The profile identifier (``external_id``).
        """
        self._delete(f"{_PATH}/{profile_id}")

    def assign(self, profile_id: int, publisher_ids: builtins.list[int]) -> dict[str, Any]:
        """Assign an upgrade profile to one or more publishers in bulk.

        Args:
            profile_id: The profile identifier (``external_id``).
            publisher_ids: Numeric IDs of the publishers to assign.

        Returns:
            The raw API response body.

        Raises:
            netskope.exceptions.ValidationError: If *publisher_ids* is empty or
                any identifier is unsafe to send.
        """
        body = self._put(_BULK_PATH, json=_build_assign_payload(profile_id, publisher_ids))
        return body


class AsyncUpgradeProfilesResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/publisherupgradeprofiles``."""

    @cached_property
    def with_response(self) -> AsyncUpgradeProfileResponses:
        """Inspect a query's completed response and its typed result."""
        return AsyncUpgradeProfileResponses(self._transport)

    async def list(self) -> builtins.list[PublisherUpgradeProfile]:
        """List all publisher upgrade profiles."""
        return (await self.with_response.list()).parse()

    async def get(self, profile_id: int) -> PublisherUpgradeProfile:
        """Get an upgrade profile by ID."""
        body = await self._get(f"{_PATH}/{profile_id}")
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    async def create(
        self,
        name: str,
        *,
        docker_tag: str,
        frequency: str,
        timezone: str,
        release_type: str,
        enabled: bool = True,
    ) -> PublisherUpgradeProfile:
        """Create a publisher upgrade profile.

        See :meth:`UpgradeProfilesResource.create`.
        """
        payload = _build_create_payload(
            name, docker_tag, frequency, timezone, release_type, enabled
        )
        body = await self._post(_PATH, json=payload)
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    async def update(
        self,
        profile_id: int,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        docker_tag: str | None = None,
        frequency: str | None = None,
        timezone: str | None = None,
        release_type: str | None = None,
    ) -> PublisherUpgradeProfile:
        """Update an upgrade profile (read-modify-write).

        See :meth:`UpgradeProfilesResource.update`.
        """
        if release_type is not None:
            _validate_release_type(release_type)
        current = await self.get(profile_id)
        payload = _build_update_payload(
            profile_id, current, name, enabled, docker_tag, frequency, timezone, release_type
        )
        body = await self._put(f"{_PATH}/{profile_id}", json=payload)
        return PublisherUpgradeProfile.model_validate(extract_item(body))

    async def delete(self, profile_id: int) -> None:
        """Delete an upgrade profile."""
        await self._delete(f"{_PATH}/{profile_id}")

    async def assign(self, profile_id: int, publisher_ids: builtins.list[int]) -> dict[str, Any]:
        """Assign an upgrade profile to publishers in bulk.

        See :meth:`UpgradeProfilesResource.assign`.
        """
        body = await self._put(_BULK_PATH, json=_build_assign_payload(profile_id, publisher_ids))
        return body
