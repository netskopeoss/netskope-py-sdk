"""Publishers resource — manage private-access gateway publishers.

Example::

    for pub in client.publishers.list():
        print(f"{pub.publisher_name} — status={pub.status}")

    new_pub = client.publishers.create(name="aws-us-east-1")
    token = client.publishers.create_registration_token(new_pub.publisher_id)
"""

from __future__ import annotations

import builtins
from functools import cached_property
from typing import Any, cast

from netskope.core.ids import extract_item, extract_list, validate_id
from netskope.core.pagination import (
    AsyncPaginatedResponse,
    Page,
    SyncPaginatedResponse,
)
from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.models.publishers import (
    Publisher,
    PublisherAlertEventType,
    PublisherAlertsConfiguration,
    PublisherAlertsConfigurationStatus,
    PublisherRelease,
)
from netskope.resources.publishers.decoder import AsyncPublisherResponses, PublisherResponses
from netskope.resources.publishers.paths import (
    _ALERTS_CONFIG_PATH,
    _PATH,
    _build_list_params,
    _parse_publishers_page,
)

# Literal sub-paths — these must never be built via the /{id} route.


# The gateway spells the local-broker flag ``lbrokerconnect``, with no
# separator: ``publisher_post_request`` (npa_publishers.yaml:323-326),
# ``publisher_patch_request`` (:354) and ``publisher_put_request`` (:368) all
# declare it that way, and a ``lbroker_connect`` key is dropped on arrival.
# Callers keep the Pythonic spelling; the rename happens once, here.


def _build_alerts_config_payload(
    admin_users: builtins.list[str] | None,
    event_types: builtins.list[str] | None,
    selected_users: str | builtins.list[str] | None = None,
) -> dict[str, Any]:
    """Build the alerts PUT body under the API's camelCase keys.

    ``publishers_alert_put_request`` (npa_publishers.yaml:589-629) declares
    ``adminUsers``, ``eventTypes`` and ``selectedUsers`` required (:591-594) and
    bounds ``eventTypes`` to 1..5 entries (:624-625).  ``selectedUsers`` is one
    comma-joined string (:627-629), so a list is joined here.  The PUT replaces
    the whole configuration, so all three are required before the request is
    built: a partial body asks the gateway to store a configuration the caller
    never described.
    """
    if event_types is not None:
        valid = {member.value for member in PublisherAlertEventType}
        invalid = [event for event in event_types if event not in valid]
        if invalid:
            raise ValidationError(
                f"Invalid event_types value(s): {', '.join(invalid)}. "
                f"Must be one of: {', '.join(sorted(valid))}"
            )
        if not 1 <= len(event_types) <= 5:
            raise ValidationError(
                f"event_types must name between 1 and 5 event types; got {len(event_types)}."
            )
    missing = [
        keyword
        for keyword, value in (
            ("admin_users", admin_users),
            ("event_types", event_types),
            ("selected_users", selected_users),
        )
        if value is None
    ]
    if missing:
        raise ValidationError(
            f"update_alerts_configuration() requires {', '.join(missing)}: "
            "publishers_alert_put_request declares adminUsers, eventTypes and "
            "selectedUsers required (npa_publishers.yaml:591-594), and the PUT "
            "replaces the whole configuration."
        )
    return {
        "adminUsers": list(admin_users or []),
        "eventTypes": [str(event) for event in event_types or []],
        "selectedUsers": (
            ",".join(selected_users) if isinstance(selected_users, list) else selected_users
        ),
    }


class PublishersResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/publishers``."""

    @cached_property
    def with_response(self) -> PublisherResponses:
        """Inspect the original response and parse its typed result from one request."""

        return PublisherResponses(self._transport)

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Publisher]:
        """List all publishers.

        Note:
            ``getNPAPublishers`` declares exactly one query parameter,
            ``fields`` (``npa_publishers.yaml:1024-1032``); no ``filter``, no
            ``offset``, no ``limit``.  The envelope's ``total`` (``:877-879``)
            reports the size of the collection; it does not establish an offset
            window the operation never declared.  The whole collection is
            therefore fetched in one request and iterated; *page_size* is
            accepted for signature compatibility and is not sent.

        Args:
            filter_expr: Unsupported; the operation declares no ``filter``.
                Any non-``None`` value raises rather than being dropped on
                arrival.
            fields: Specific fields to include in each record.
            page_size: Unused; the operation declares no ``limit``.

        Returns:
            A lazy iterator of
            :class:`~netskope.models.publishers.Publisher` over the one
            collection response.

        Raises:
            netskope.exceptions.ValidationError: If *filter_expr* is supplied.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(filter_expr, fields),
            model=Publisher,
            page_size=page_size,
            parse_page=_parse_publishers_page,
            paginated=False,
        )

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Page[Publisher]:
        """Fetch one window of the collection, applying *offset*/*limit* locally.

        ``getNPAPublishers`` declares neither parameter
        (``npa_publishers.yaml:1024-1032``), so the request carries only
        ``fields``, the gateway answers with the whole collection, and the
        window is applied to the records in hand.  The page retains the
        envelope metadata and its stated ``total``, so ``has_more`` still
        describes the records outside the window.

        Raises:
            netskope.exceptions.ValidationError: If *filter_expr* is supplied,
                or *offset*/*limit* is not a usable window bound.
        """
        return self.with_response.list_page(
            filter_expr=filter_expr, fields=fields, offset=offset, limit=limit
        ).parse()

    def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID.

        Args:
            publisher_id: The numeric publisher identifier.
        """
        return self.with_response.get(publisher_id).parse()

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
        return self.with_response.create(
            name, lbroker_connect=lbroker_connect, extra_fields=extra_fields
        ).parse()

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
            name: New name (sent as ``name``).  Required unless *extra_fields*
                carries one: ``publisher_patch_request`` declares
                ``required: [name]`` (``npa_publishers.yaml:338-341``).
            extra_fields: Optional additional settings to update.

        Raises:
            netskope.exceptions.ValidationError: If no ``name`` is supplied by
                either argument.
        """
        return self.with_response.update(publisher_id, name=name, extra_fields=extra_fields).parse()

    def delete(self, publisher_id: int) -> None:
        """Delete a publisher.

        Args:
            publisher_id: The publisher identifier.
        """
        self._delete(f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}")

    def list_apps(self, publisher_id: int) -> builtins.list[dict[str, Any]]:
        """List private apps associated with a publisher.

        Args:
            publisher_id: The publisher identifier.

        Returns:
            A list of raw app records.
        """
        response = self.with_response.list_apps(publisher_id)
        return extract_list(response.json(), "apps")

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
        return self.with_response.create_registration_token(publisher_id).parse()

    def list_releases(self) -> builtins.list[PublisherRelease]:
        """List available publisher software releases.

        Returns:
            A list of :class:`~netskope.models.publishers.PublisherRelease`.
        """
        return self.with_response.list_releases().parse()

    def bulk_upgrade(self, publisher_ids: builtins.list[int | str]) -> dict[str, Any]:
        """Trigger an upgrade for one or more publishers.

        Args:
            publisher_ids: IDs of the publishers to upgrade.  The API
                takes them as strings, so numbers are stringified.

        Returns:
            The raw API response body.
        """
        return cast(dict[str, Any], self.with_response.bulk_upgrade(publisher_ids).json())

    def get_alerts_configuration(self) -> PublisherAlertsConfiguration:
        """Get the publisher alert notification configuration."""
        body = self._get(_ALERTS_CONFIG_PATH)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))

    def update_alerts_configuration(
        self,
        *,
        admin_users: builtins.list[str] | None = None,
        event_types: builtins.list[str] | None = None,
        selected_users: str | builtins.list[str] | None = None,
    ) -> PublisherAlertsConfigurationStatus:
        """Replace the publisher alert notification configuration (PUT).

        The gateway declares all three keys required
        (``npa_publishers.yaml:591-594``) and the PUT replaces the whole
        configuration, so all three must be supplied.

        ``publishers_alert_put_response`` (``:630-638``) carries a ``status``
        and nothing else, so the return value is that acknowledgment, not the
        stored configuration.  Call :meth:`get_alerts_configuration` to read
        back what the gateway kept.

        Args:
            admin_users: Admin email addresses to notify (sent as
                ``adminUsers``).  Required.
            event_types: Between one and five event types that trigger
                notifications (sent as ``eventTypes``).  Required.  Values must
                be members of
                :class:`~netskope.models.publishers.PublisherAlertEventType`.
            selected_users: Recipients the alert is addressed to, as one
                comma-joined string or a list joined into one (sent as
                ``selectedUsers``).  Required.

        Raises:
            netskope.exceptions.ValidationError: If any of the three is
                omitted, or *event_types* contains an unsupported value or
                names fewer than one or more than five event types.
        """
        payload = _build_alerts_config_payload(admin_users, event_types, selected_users)
        body = self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfigurationStatus.model_validate(extract_item(body))


class AsyncPublishersResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/publishers``."""

    @cached_property
    def with_response(self) -> AsyncPublisherResponses:
        """Inspect the original response and parse its typed result from one request."""

        return AsyncPublisherResponses(self._transport)

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[Publisher]:
        """List all publishers.  See :meth:`PublishersResource.list`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(filter_expr, fields),
            model=Publisher,
            page_size=page_size,
            parse_page=_parse_publishers_page,
            paginated=False,
        )

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Page[Publisher]:
        """Fetch one locally-applied window.  See :meth:`PublishersResource.list_page`."""
        response = await self.with_response.list_page(
            filter_expr=filter_expr, fields=fields, offset=offset, limit=limit
        )
        return response.parse()

    async def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID."""
        return (await self.with_response.get(publisher_id)).parse()

    async def create(
        self,
        name: str,
        *,
        lbroker_connect: bool = False,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Register a new publisher."""
        response = await self.with_response.create(
            name, lbroker_connect=lbroker_connect, extra_fields=extra_fields
        )
        return response.parse()

    async def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Update a publisher (PATCH)."""
        response = await self.with_response.update(
            publisher_id, name=name, extra_fields=extra_fields
        )
        return response.parse()

    async def delete(self, publisher_id: int) -> None:
        """Delete a publisher."""
        await self._delete(f"{_PATH}/{validate_id(publisher_id, 'publisher_id')}")

    async def list_apps(self, publisher_id: int) -> builtins.list[dict[str, Any]]:
        """List private apps associated with a publisher."""
        response = await self.with_response.list_apps(publisher_id)
        return extract_list(response.json(), "apps")

    async def create_registration_token(self, publisher_id: int) -> str:
        """Generate a registration token for a publisher.

        See :meth:`PublishersResource.create_registration_token`.
        """
        return (await self.with_response.create_registration_token(publisher_id)).parse()

    async def list_releases(self) -> builtins.list[PublisherRelease]:
        """List available publisher software releases."""
        return (await self.with_response.list_releases()).parse()

    async def bulk_upgrade(self, publisher_ids: builtins.list[int | str]) -> dict[str, Any]:
        """Trigger an upgrade for one or more publishers.

        See :meth:`PublishersResource.bulk_upgrade`.
        """
        response = await self.with_response.bulk_upgrade(publisher_ids)
        return cast(dict[str, Any], response.json())

    async def get_alerts_configuration(self) -> PublisherAlertsConfiguration:
        """Get the publisher alert notification configuration."""
        body = await self._get(_ALERTS_CONFIG_PATH)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))

    async def update_alerts_configuration(
        self,
        *,
        admin_users: builtins.list[str] | None = None,
        event_types: builtins.list[str] | None = None,
        selected_users: str | builtins.list[str] | None = None,
    ) -> PublisherAlertsConfigurationStatus:
        """Replace the publisher alert notification configuration (PUT).

        See :meth:`PublishersResource.update_alerts_configuration`.
        """
        payload = _build_alerts_config_payload(admin_users, event_types, selected_users)
        body = await self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfigurationStatus.model_validate(extract_item(body))
