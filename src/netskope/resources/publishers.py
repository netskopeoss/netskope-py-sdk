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
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError as PydanticValidationError

from netskope._pagination import AsyncPaginatedResponse, Page, SyncPaginatedResponse, _make_page
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.publishers import (
    Publisher,
    PublisherAlertEventType,
    PublisherAlertsConfiguration,
    PublisherCreate,
    PublisherRelease,
    PublisherUpdate,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, id_strings

if TYPE_CHECKING:
    from netskope.resources._publisher_response import AsyncPublisherResponses, PublisherResponses

_PATH = "/api/v2/infrastructure/publishers"

# Literal sub-paths — these must never be built via the /{id} route.
_RELEASES_PATH = f"{_PATH}/releases"
_BULK_PATH = f"{_PATH}/bulk"
_ALERTS_CONFIG_PATH = f"{_PATH}/alertsconfiguration"


def _parse_publishers_page(body: Any, offset: int, limit: int | None) -> Page[Publisher]:
    """Decode publisher records and retain metadata without retaining their raw bodies."""
    metadata: dict[str, Any] = {}
    if isinstance(body, list):
        records = body
    elif isinstance(body, dict):
        metadata = dict(body)
        if isinstance(body.get("result"), list):
            records = metadata.pop("result")
        elif isinstance(body.get("data"), list):
            records = metadata.pop("data")
        elif isinstance(body.get("data"), dict) and "publishers" in body["data"]:
            nested = dict(body["data"])
            records = nested.pop("publishers")
            if nested:
                metadata["data"] = nested
            else:
                metadata.pop("data")
        elif "publishers" in body:
            records = metadata.pop("publishers")
        elif isinstance(body.get("Resources"), list):
            records = metadata.pop("Resources")
        else:
            raise ResponseValidationError(
                "Invalid publishers response: expected a publisher collection."
            )
    else:
        raise ResponseValidationError("Invalid publishers response: expected an object or list.")

    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ResponseValidationError(
            "Invalid publishers response: expected a list of publisher objects."
        )
    items = [Publisher.model_validate(item) for item in records]
    return _make_page(items, metadata, offset, limit)


def _extract_publisher(body: dict[str, Any]) -> Publisher:
    if not isinstance(body, dict):
        raise ResponseValidationError("Invalid publisher response: expected a publisher object.")
    data = body.get("data", body)
    if isinstance(data, dict) and "publishers" in data:
        items = data["publishers"]
        if not isinstance(items, list) or len(items) != 1:
            raise ResponseValidationError(
                "Invalid publisher response: expected one publisher object."
            )
        data = items[0]
    if not isinstance(data, dict) or not data:
        raise ResponseValidationError("Invalid publisher response: expected a publisher object.")
    return Publisher.model_validate(data)


def _extract_token(body: dict[str, Any]) -> str:
    if not isinstance(body, dict):
        raise ResponseValidationError("Registration token missing from response.")
    data = body.get("data")
    if isinstance(data, dict) and data.get("token") is not None:
        return str(data["token"])
    if body.get("token") is not None:
        return str(body["token"])
    raise ResponseValidationError("Registration token missing from response.")


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


def _build_page_params(
    filter_expr: str | None,
    fields: builtins.list[str] | None,
    offset: int | None,
    limit: int | None,
) -> dict[str, Any]:
    params = _build_list_params(filter_expr, fields)
    for name, value, minimum in (("offset", offset, 0), ("limit", limit, 1)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValidationError(f"Invalid {name}: expected an integer >= {minimum}.")
        params[name] = value
    return params


# The gateway spells the local-broker flag ``lbrokerconnect``, with no
# separator: ``publisher_post_request`` (npa_publishers.yaml:323-326),
# ``publisher_patch_request`` (:354) and ``publisher_put_request`` (:368) all
# declare it that way, and a ``lbroker_connect`` key is dropped on arrival.
# Callers keep the Pythonic spelling; the rename happens once, here.
_WIRE_NAMES = {"lbroker_connect": "lbrokerconnect"}


def _to_wire(payload: dict[str, Any]) -> dict[str, Any]:
    """Rename the fields whose gateway spelling differs from the SDK's."""
    return {_WIRE_NAMES.get(key, key): value for key, value in payload.items()}


def _validate_publisher_payload(
    payload: dict[str, Any],
    model: type[PublisherCreate] | type[PublisherUpdate],
) -> dict[str, Any]:
    known_fields = {key: value for key, value in payload.items() if key in model.model_fields}
    try:
        request = model.model_validate(known_fields)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc)) from exc
    return _to_wire({**payload, **request.model_dump(mode="json", exclude_unset=True)})


def _build_create_payload(
    name: str,
    lbroker_connect: bool,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "lbroker_connect": lbroker_connect}
    if extra_fields:
        payload.update(extra_fields)
    return _validate_publisher_payload(payload, PublisherCreate)


def _build_update_payload(
    name: str | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if extra_fields:
        payload.update(extra_fields)
    if not payload:
        raise ValidationError("update() requires name or at least one extra field to change.")
    return _validate_publisher_payload(payload, PublisherUpdate)


def _build_bulk_upgrade_payload(publisher_ids: builtins.list[int | str]) -> dict[str, Any]:
    """Build the bulk-upgrade body, whose ids the gateway takes as strings.

    ``publishers_bulk_request.publishers.id.items`` is ``{type: string}``
    (npa_publishers.yaml:294-299), and the endpoint's own examples send
    ``["12"]`` (:1230-1244).  The sibling ``publisherupgradeprofiles/bulk``
    endpoint already sends strings.
    """
    if not isinstance(publisher_ids, list):
        raise ValidationError("publisher_ids must be a list of publisher IDs.")
    return {
        "publishers": {
            "apply": {"upgrade_request": True},
            "id": id_strings(publisher_ids, "publisher_ids"),
        }
    }


def _build_alerts_config_payload(
    admin_users: builtins.list[str] | None,
    event_types: builtins.list[str] | None,
    selected_users: str | builtins.list[str] | None = None,
) -> dict[str, Any]:
    """Build the alerts PUT body under the API's camelCase keys.

    ``publishers_alert_put_request`` (npa_publishers.yaml:589-629) declares
    ``adminUsers``, ``eventTypes`` and ``selectedUsers`` required and bounds
    ``eventTypes`` to 1..5 entries (:624-625).  ``selectedUsers`` is one
    comma-joined string (:627-629), so a list is joined here.
    """
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
        if not 1 <= len(event_types) <= 5:
            raise ValidationError(
                f"event_types must name between 1 and 5 event types; got {len(event_types)}."
            )
        payload["eventTypes"] = [str(event) for event in event_types]
    if selected_users is not None:
        payload["selectedUsers"] = (
            ",".join(selected_users) if isinstance(selected_users, list) else selected_users
        )
    return payload


class PublishersResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/publishers``."""

    @cached_property
    def with_response(self) -> PublisherResponses:
        """Inspect the original response and parse its typed result from one request."""
        from netskope.resources._publisher_response import PublisherResponses

        return PublisherResponses(self._transport)

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[Publisher]:
        """List all publishers with automatic pagination.

        Note:
            ``getNPAPublishers`` documents one query parameter, ``fields``
            (``npa_publishers.yaml:1025-1033``).  ``filter``, ``offset`` and
            ``limit`` are undocumented; the list envelope does report ``total``
            (``:877-879``), so pagination works, but a tenant that ignores
            these parameters answers with the unfiltered first page.

        Args:
            filter_expr: Filter expression to narrow results
                (API-specific syntax, sent as ``filter``; undocumented).
            fields: Specific fields to include in each record.
            page_size: Results per page (sent as ``limit``; undocumented).

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
            parse_page=_parse_publishers_page,
        )

    def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Page[Publisher]:
        """Fetch one page, preserving API defaults for omitted pagination parameters.

        The result retains envelope metadata and any stated total. An
        unknown total does not establish whether more records exist.
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
            name: New name (optional, sent as ``name``).
            extra_fields: Optional additional settings to update.
        """
        return self.with_response.update(publisher_id, name=name, extra_fields=extra_fields).parse()

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
    ) -> PublisherAlertsConfiguration:
        """Update the publisher alert notification configuration.

        The gateway declares all three keys required on this PUT
        (``npa_publishers.yaml:589-594``), so a partial body may be rejected;
        supply everything the configuration should end up with.

        Args:
            admin_users: Admin email addresses to notify (sent as
                ``adminUsers``).
            event_types: Between one and five event types that trigger
                notifications (sent as ``eventTypes``).  Values must be
                members of
                :class:`~netskope.models.publishers.PublisherAlertEventType`.
            selected_users: Recipients the alert is addressed to, as one
                comma-joined string or a list joined into one (sent as
                ``selectedUsers``).

        Raises:
            netskope.exceptions.ValidationError: If *event_types* contains an
                unsupported value or names fewer than one or more than five
                event types.
        """
        payload = _build_alerts_config_payload(admin_users, event_types, selected_users)
        body = self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))


class AsyncPublishersResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/publishers``."""

    @cached_property
    def with_response(self) -> AsyncPublisherResponses:
        """Inspect the original response and parse its typed result from one request."""
        from netskope.resources._publisher_response import AsyncPublisherResponses

        return AsyncPublisherResponses(self._transport)

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
            parse_page=_parse_publishers_page,
        )

    async def list_page(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Page[Publisher]:
        """Fetch one page with metadata, leaving omitted pagination values to the API."""
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
        await self._delete(f"{_PATH}/{publisher_id}")

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
    ) -> PublisherAlertsConfiguration:
        """Update the publisher alert notification configuration.

        See :meth:`PublishersResource.update_alerts_configuration`.
        """
        payload = _build_alerts_config_payload(admin_users, event_types, selected_users)
        body = await self._put(_ALERTS_CONFIG_PATH, json=payload)
        return PublisherAlertsConfiguration.model_validate(extract_item(body))
