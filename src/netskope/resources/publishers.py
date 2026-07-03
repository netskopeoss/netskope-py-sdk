"""Publishers resource — manage private-access gateway publishers.

Example::

    for pub in client.publishers.list():
        print(f"{pub.publisher_name} — status={pub.status}")

    new_pub = client.publishers.create(name="aws-us-east-1")
    token = client.publishers.create_registration_token(new_pub.publisher_id)
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import NetskopeError, ValidationError
from netskope.models.publishers import (
    Publisher,
    PublisherAlertEventType,
    PublisherAlertsConfiguration,
    PublisherRelease,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list

_PATH = "/api/v2/infrastructure/publishers"

# Literal sub-paths — these must never be built via the /{id} route.
_RELEASES_PATH = f"{_PATH}/releases"
_BULK_PATH = f"{_PATH}/bulk"
_ALERTS_CONFIG_PATH = f"{_PATH}/alertsconfiguration"


def _extract_publishers(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "publishers")


def _extract_publisher(body: dict[str, Any]) -> Publisher:
    data = body.get("data", body)
    if isinstance(data, dict) and "publishers" in data:
        items = data["publishers"]
        if items:
            return Publisher.model_validate(items[0])
    return Publisher.model_validate(data)


def _extract_token(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, dict) and data.get("token") is not None:
        return str(data["token"])
    if body.get("token") is not None:
        return str(body["token"])
    raise NetskopeError(f"Registration token missing from response: {body!r}")


def _build_list_params(
    filter_expr: str | None,
    fields: builtins.list[str] | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if filter_expr is not None:
        params["filter"] = filter_expr
    if fields:
        params["fields"] = ",".join(fields)
    return params


def _build_create_payload(
    name: str,
    lbroker_connect: bool,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "lbroker_connect": lbroker_connect}
    if extra_fields:
        payload.update(extra_fields)
    return payload


def _build_update_payload(
    name: str | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if extra_fields:
        payload.update(extra_fields)
    return payload


def _build_bulk_upgrade_payload(publisher_ids: builtins.list[int]) -> dict[str, Any]:
    return {
        "publishers": {
            "apply": {"upgrade_request": True},
            "id": [int(publisher_id) for publisher_id in publisher_ids],
        }
    }


def _build_alerts_config_payload(
    admin_users: builtins.list[str] | None,
    event_types: builtins.list[str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if admin_users is not None:
        payload["adminUsers"] = list(admin_users)
    if event_types is not None:
        valid = {member.value for member in PublisherAlertEventType}
        invalid = [event for event in event_types if event not in valid]
        if invalid:
            raise ValidationError(
                f"Invalid event_types value(s): {', '.join(invalid)}. "
                f"Must be one of: {', '.join(sorted(valid))}"
            )
        payload["eventTypes"] = [str(event) for event in event_types]
    return payload


class PublishersResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/publishers``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Publisher]:
        """List all publishers with automatic pagination.

        Args:
            filter_expr: Filter expression to narrow results
                (API-specific syntax, sent as ``filter``).
            fields: Specific fields to include in each record.
            page_size: Results per page.

        Returns:
            A lazy paginated iterator of
            :class:`~netskope.models.publishers.Publisher`.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(filter_expr, fields),
            model=Publisher,
            page_size=page_size,
            extract=_extract_publishers,
        )

    def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID.

        Args:
            publisher_id: The numeric publisher identifier.
        """
        body = self._get(f"{_PATH}/{publisher_id}")
        return _extract_publisher(body)

    def create(
        self,
        name: str,
        *,
        lbroker_connect: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Register a new publisher.

        Args:
            name: Human-readable publisher name (sent as ``name``).
            lbroker_connect: Enable local broker connectivity (default False).
            extra_fields: Optional additional publisher settings.
        """
        payload = _build_create_payload(name, lbroker_connect, extra_fields)
        body = self._post(_PATH, json=payload)
        return _extract_publisher(body)

    def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Update a publisher (PATCH).

        Args:
            publisher_id: The publisher identifier.
            name: New name (optional, sent as ``name``).
            extra_fields: Optional additional settings to update.
        """
        payload = _build_update_payload(name, extra_fields)
        body = self._patch(f"{_PATH}/{publisher_id}", json=payload)
        return _extract_publisher(body)

    def delete(self, publisher_id: int) -> None:
        """Delete a publisher.

        Args:
            publisher_id: The publisher identifier.
        """
        self._delete(f"{_PATH}/{publisher_id}")

    def list_apps(self, publisher_id: int) -> builtins.list[dict[str, Any]]:
        """List private apps associated with a publisher.

        Args:
            publisher_id: The publisher identifier.

        Returns:
            A list of raw app records.
        """
        body = self._get(f"{_PATH}/{publisher_id}/apps")
        return extract_list(body, "apps")

    def create_registration_token(self, publisher_id: int) -> str:
        """Generate a registration token for a publisher.

        Args:
            publisher_id: The publisher identifier.

        Returns:
            The registration token string.

        Raises:
            netskope.exceptions.NetskopeError: If no token is present in
                the response.
        """
        body = self._post(f"{_PATH}/{publisher_id}/registration_token")
        return _extract_token(body)

    def list_releases(self) -> builtins.list[PublisherRelease]:
        """List available publisher software releases.

        Returns:
            A list of :class:`~netskope.models.publishers.PublisherRelease`.
        """
        body = self._get(_RELEASES_PATH)
        return [PublisherRelease.model_validate(item) for item in extract_list(body, "releases")]

    def bulk_upgrade(self, publisher_ids: builtins.list[int]) -> dict[str, Any]:
        """Trigger an upgrade for one or more publishers.

        Args:
            publisher_ids: Numeric IDs of the publishers to upgrade.

        Returns:
            The raw API response body.
        """
        body = self._put(_BULK_PATH, json=_build_bulk_upgrade_payload(publisher_ids))
        return body

    def get_alerts_configuration(self) -> PublisherAlertsConfiguration:
        """Get the publisher alert notification configuration."""
        body = self._get(_ALERTS_CONFIG_PATH)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))

    def update_alerts_configuration(
        self,
        *,
        admin_users: builtins.list[str] | None = None,
        event_types: builtins.list[str] | None = None,
    ) -> PublisherAlertsConfiguration:
        """Update the publisher alert notification configuration.

        Args:
            admin_users: Admin email addresses to notify (sent as
                ``adminUsers``).
            event_types: Event types that trigger notifications (sent as
                ``eventTypes``).  Values must be members of
                :class:`~netskope.models.publishers.PublisherAlertEventType`.

        Raises:
            netskope.exceptions.ValidationError: If *event_types* contains
                an unsupported value.
        """
        payload = _build_alerts_config_payload(admin_users, event_types)
        body = self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))


class AsyncPublishersResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/publishers``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Publisher]:
        """List all publishers with automatic pagination."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(filter_expr, fields),
            model=Publisher,
            page_size=page_size,
            extract=_extract_publishers,
        )

    async def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID."""
        body = await self._get(f"{_PATH}/{publisher_id}")
        return _extract_publisher(body)

    async def create(
        self,
        name: str,
        *,
        lbroker_connect: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Register a new publisher."""
        payload = _build_create_payload(name, lbroker_connect, extra_fields)
        body = await self._post(_PATH, json=payload)
        return _extract_publisher(body)

    async def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Update a publisher (PATCH)."""
        payload = _build_update_payload(name, extra_fields)
        body = await self._patch(f"{_PATH}/{publisher_id}", json=payload)
        return _extract_publisher(body)

    async def delete(self, publisher_id: int) -> None:
        """Delete a publisher."""
        await self._delete(f"{_PATH}/{publisher_id}")

    async def list_apps(self, publisher_id: int) -> builtins.list[dict[str, Any]]:
        """List private apps associated with a publisher."""
        body = await self._get(f"{_PATH}/{publisher_id}/apps")
        return extract_list(body, "apps")

    async def create_registration_token(self, publisher_id: int) -> str:
        """Generate a registration token for a publisher.

        See :meth:`PublishersResource.create_registration_token`.
        """
        body = await self._post(f"{_PATH}/{publisher_id}/registration_token")
        return _extract_token(body)

    async def list_releases(self) -> builtins.list[PublisherRelease]:
        """List available publisher software releases."""
        body = await self._get(_RELEASES_PATH)
        return [PublisherRelease.model_validate(item) for item in extract_list(body, "releases")]

    async def bulk_upgrade(self, publisher_ids: builtins.list[int]) -> dict[str, Any]:
        """Trigger an upgrade for one or more publishers.

        See :meth:`PublishersResource.bulk_upgrade`.
        """
        body = await self._put(_BULK_PATH, json=_build_bulk_upgrade_payload(publisher_ids))
        return body

    async def get_alerts_configuration(self) -> PublisherAlertsConfiguration:
        """Get the publisher alert notification configuration."""
        body = await self._get(_ALERTS_CONFIG_PATH)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))

    async def update_alerts_configuration(
        self,
        *,
        admin_users: builtins.list[str] | None = None,
        event_types: builtins.list[str] | None = None,
    ) -> PublisherAlertsConfiguration:
        """Update the publisher alert notification configuration.

        See :meth:`PublishersResource.update_alerts_configuration`.
        """
        payload = _build_alerts_config_payload(admin_users, event_types)
        body = await self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))
