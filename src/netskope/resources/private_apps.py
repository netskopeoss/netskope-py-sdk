"""Private Apps resource — manage ZTNA private applications.

Example::

    for app in client.private_apps.list(in_policy=True):
        print(f"{app.app_name} → {app.host}:{app.port}")

    new_app = client.private_apps.create(
        name="internal-dashboard",
        host="10.0.0.5",
        port="443",
        protocols=["TCP"],
        publisher_ids=[1, 2],
    )

    # Tags
    for tag in client.private_apps.tags.list():
        print(f"{tag.tag_id}: {tag.tag_name}")
"""

from __future__ import annotations

import builtins
import functools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from netskope.resources._private_app_response import (
        AsyncPrivateAppResponses,
        AsyncPrivateAppTagResponses,
        PrivateAppResponses,
        PrivateAppTagResponses,
    )

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ValidationError
from netskope.models._npa_requests import request_payload
from netskope.models.private_apps import (
    PrivateApp,
    PrivateAppCreate,
    PrivateAppProtocol,
    PrivateAppTag,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, id_strings, validate_id

# ``TCP/UDP`` selects both transports; the API carries one entry per transport.
_PROTOCOL_TRANSPORTS: dict[str, tuple[str, ...]] = {
    PrivateAppProtocol.TCP.value.lower(): ("tcp",),
    PrivateAppProtocol.UDP.value.lower(): ("udp",),
    PrivateAppProtocol.TCP_UDP.value.lower(): ("tcp", "udp"),
}

_PATH = "/api/v2/steering/apps/private"
_TAGS_PATH = f"{_PATH}/tags"
_PUBLISHERS_PATH = f"{_PATH}/publishers"
_DISCOVERY_PATH = f"{_PATH}/discoverysettings"
_POLICY_IN_USE_PATH = f"{_PATH}/getpolicyinuse"
_TAGS_POLICY_IN_USE_PATH = f"{_TAGS_PATH}/getpolicyinuse"


def _extract(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data", [])
    if isinstance(data, dict):
        apps = data.get("private_apps", [])
        if isinstance(apps, list):
            return apps
    if isinstance(data, list):
        return data
    return []


def _extract_tags(body: dict[str, Any]) -> list[dict[str, Any]]:
    return extract_list(body, "tags")


def _query_term(name: str, operator: str, value: Any) -> str:
    """Render one ``<column> <operator> <value>`` term of a query expression."""
    return f"{name} {operator} {value}"


def _filter_terms(
    app_name: str | None,
    publisher_name: str | None,
    reachable: bool | None,
    clientless_access: bool | None,
    host: str | None,
    in_policy: bool | None,
    protocol: str | None,
) -> builtins.list[str]:
    """Translate the convenience filters into the query terms the API names.

    ``listNPAPrivateApps`` declares exactly ``fields``, ``query``, ``offset``
    and ``limit`` (npa_apps_private.yaml:490-524); every attribute below is a
    *term inside* ``query``, with the operators and value spellings documented
    in npa_generic.yaml:495-504 — ``yes``/``no`` for ``reachable`` and
    ``in_policy``, ``true``/``false`` for ``clientless_access``.  Sent as bare
    parameters they were dropped on arrival and the caller silently got an
    unfiltered collection.
    """
    terms: builtins.list[str] = []
    if app_name is not None:
        terms.append(_query_term("name", "sw", app_name))
    if publisher_name is not None:
        terms.append(_query_term("publisher_name", "eq", publisher_name))
    if host is not None:
        terms.append(_query_term("host", "eq", host))
    if protocol is not None:
        terms.append(_query_term("private_app_protocol", "eq", protocol))
    if reachable is not None:
        terms.append(_query_term("reachable", "eq", "yes" if reachable else "no"))
    if in_policy is not None:
        terms.append(_query_term("in_policy", "eq", "yes" if in_policy else "no"))
    if clientless_access is not None:
        terms.append(
            _query_term("clientless_access", "eq", "true" if clientless_access else "false")
        )
    return terms


def _build_list_params(
    query: str | None,
    app_name: str | None,
    publisher_name: str | None,
    reachable: bool | None,
    clientless_access: bool | None,
    host: str | None,
    in_policy: bool | None,
    protocol: str | None,
    filter_expr: str | None,
    fields: builtins.list[str] | None,
) -> dict[str, Any]:
    """Build the four query parameters the private-apps list endpoint declares.

    A caller's own *query* and *filter_expr* expressions lead, in that order,
    and the convenience filters are appended as further ``and`` terms.
    """
    expressions = [expression for expression in (query, filter_expr) if expression] + _filter_terms(
        app_name, publisher_name, reachable, clientless_access, host, in_policy, protocol
    )
    params: dict[str, Any] = {}
    if expressions:
        params["query"] = " and ".join(expressions)
    if fields:
        params["fields"] = ",".join(fields)
    return params


def _port_string(port: Any) -> str:
    """Accept a port number or a port-range string, as the API's examples do."""
    text = str(port).strip() if isinstance(port, (int, str)) and not isinstance(port, bool) else ""
    if not text:
        raise ValidationError("port must be a port number or a port-range string.")
    return text


def _protocol_types(protocol: Any) -> tuple[str, ...]:
    """Map one caller-supplied transport onto the transports the API names."""
    key = protocol.strip().lower() if isinstance(protocol, str) else ""
    types = _PROTOCOL_TRANSPORTS.get(key)
    if types is None:
        accepted = ", ".join(member.value for member in PrivateAppProtocol)
        raise ValidationError(
            f"Unsupported protocol {protocol!r}. Use one of {accepted}, "
            "or a mapping of type and port."
        )
    return types


def _protocol_entries(
    protocols: builtins.list[Any],
    port: str | int,
) -> builtins.list[dict[str, Any]]:
    """Build the ``{"type", "port"}`` entries the API carries each port in.

    ``TCP/UDP`` names both transports, which the API expresses as two entries
    sharing one port.  An entry that already arrives as a mapping keeps its own
    port and any other fields, so the create schema can judge them.
    """
    entries: builtins.list[dict[str, Any]] = []
    for protocol in protocols:
        if isinstance(protocol, dict):
            entry_port = (
                _port_string(protocol["port"]) if "port" in protocol else _port_string(port)
            )
            types = _protocol_types(protocol.get("type"))
            entries.extend({**protocol, "type": name, "port": entry_port} for name in types)
        else:
            entry_port = _port_string(port)
            entries.extend({"type": name, "port": entry_port} for name in _protocol_types(protocol))
    return entries


def _build_create_payload(
    name: str,
    host: str,
    port: str | int,
    protocols: builtins.list[Any] | None,
    publisher_ids: builtins.list[int] | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the create body through :class:`PrivateAppCreate`, keeping extras.

    The API carries each port inside its protocol entry, so *port* is only
    expressible alongside *protocols*.  Fields the model does not declare come
    from *extra_fields* and pass through unvalidated, as they always have.
    """
    if not protocols:
        raise ValidationError(
            "protocols is required: the API carries the port inside each protocol entry."
        )
    payload: dict[str, Any] = {
        "app_name": name,
        "host": host,
        "protocols": _protocol_entries(protocols, port),
    }
    if publisher_ids is not None:
        payload["publishers"] = [
            {"publisher_id": publisher} for publisher in id_strings(publisher_ids, "publisher_ids")
        ]
    if extra_fields:
        payload.update(extra_fields)
    modeled = {key: value for key, value in payload.items() if key in PrivateAppCreate.model_fields}
    return {**payload, **request_payload(modeled, PrivateAppCreate)}


def _publisher_assoc_payload(
    app_ids: builtins.list[int],
    publisher_ids: builtins.list[int],
) -> dict[str, builtins.list[str]]:
    return {
        "private_app_ids": id_strings(app_ids, "app_ids"),
        "publisher_ids": id_strings(publisher_ids, "publisher_ids"),
    }


def _tag_objects(tag_names: builtins.list[str]) -> list[dict[str, str]]:
    """Name at least one tag, so a write cannot ask the API to do nothing."""
    if not tag_names:
        raise ValidationError("tag_names must not be empty.")
    if any(not isinstance(tag, str) or not tag.strip() for tag in tag_names):
        raise ValidationError("Every tag name must be a nonempty string.")
    return [{"tag_name": tag} for tag in tag_names]


def _tag_bulk_payload(
    app_ids: builtins.list[int | str],
    tag_names: builtins.list[str],
) -> dict[str, Any]:
    # The tags bulk endpoints expect app IDs as strings.
    return {"ids": id_strings(app_ids, "app_ids"), "tags": _tag_objects(tag_names)}


def _tag_create_payload(app_id: int | str, tag_names: builtins.list[str]) -> dict[str, Any]:
    # The tag create endpoint expects the app ID as a string.
    return {"id": validate_id(app_id, "app_id"), "tags": _tag_objects(tag_names)}


class PrivateAppTagsResource(SyncResource):
    """Synchronous interface to ``/api/v2/steering/apps/private/tags``."""

    @functools.cached_property
    def with_response(self) -> PrivateAppTagResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._private_app_response import PrivateAppTagResponses

        return PrivateAppTagResponses(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[PrivateAppTag]:
        """List private-app tags.

        Args:
            query: Search query string to filter tags.
            page_size: Results per page.
        """
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TAGS_PATH,
            params=params,
            model=PrivateAppTag,
            page_size=page_size,
            extract=_extract_tags,
        )

    def get(self, tag_id: int) -> PrivateAppTag:
        """Get a tag by ID."""
        body = self._get(f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}")
        return PrivateAppTag.model_validate(extract_item(body))

    def create(
        self, app_id: int | str, tag_names: builtins.list[str]
    ) -> builtins.list[PrivateAppTag]:
        """Create tags on a private application.

        Args:
            app_id: The application to attach the new tags to.
            tag_names: Names of the tags to create.
        """
        body = self._post(_TAGS_PATH, json=_tag_create_payload(app_id, tag_names))
        return [PrivateAppTag.model_validate(item) for item in extract_list(body, "tags")]

    def update(self, tag_id: int, tag_name: str) -> PrivateAppTag:
        """Rename a tag.

        Args:
            tag_id: The tag identifier.
            tag_name: The new tag name.
        """
        body = self._put(
            f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}", json={"tag_name": tag_name}
        )
        return PrivateAppTag.model_validate(extract_item(body))

    def delete(self, tag_id: int) -> None:
        """Delete a tag."""
        self._delete(f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}")

    def add(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> dict[str, Any]:
        """Add tags to multiple private applications."""
        return self._patch(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    def replace(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> dict[str, Any]:
        """Replace all tags on multiple private applications."""
        return self._put(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    def remove(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> None:
        """Remove tags from multiple private applications."""
        self._delete(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    def get_policy_in_use(self, tag_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified tags."""
        return self._post(
            _TAGS_POLICY_IN_USE_PATH, json={"ids": id_strings(tag_ids, "tag_ids")}, retry_safe=True
        )


class AsyncPrivateAppTagsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/steering/apps/private/tags``."""

    @functools.cached_property
    def with_response(self) -> AsyncPrivateAppTagResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._private_app_response import AsyncPrivateAppTagResponses

        return AsyncPrivateAppTagResponses(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[PrivateAppTag]:
        """List private-app tags."""
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_TAGS_PATH,
            params=params,
            model=PrivateAppTag,
            page_size=page_size,
            extract=_extract_tags,
        )

    async def get(self, tag_id: int) -> PrivateAppTag:
        """Get a tag by ID."""
        body = await self._get(f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}")
        return PrivateAppTag.model_validate(extract_item(body))

    async def create(
        self, app_id: int | str, tag_names: builtins.list[str]
    ) -> builtins.list[PrivateAppTag]:
        """Create tags on a private application."""
        body = await self._post(_TAGS_PATH, json=_tag_create_payload(app_id, tag_names))
        return [PrivateAppTag.model_validate(item) for item in extract_list(body, "tags")]

    async def update(self, tag_id: int, tag_name: str) -> PrivateAppTag:
        """Rename a tag."""
        body = await self._put(
            f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}", json={"tag_name": tag_name}
        )
        return PrivateAppTag.model_validate(extract_item(body))

    async def delete(self, tag_id: int) -> None:
        """Delete a tag."""
        await self._delete(f"{_TAGS_PATH}/{validate_id(tag_id, 'tag_id')}")

    async def add(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> dict[str, Any]:
        """Add tags to multiple private applications."""
        return await self._patch(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    async def replace(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> dict[str, Any]:
        """Replace all tags on multiple private applications."""
        return await self._put(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    async def remove(
        self,
        app_ids: builtins.list[int | str],
        tag_names: builtins.list[str],
    ) -> None:
        """Remove tags from multiple private applications."""
        await self._delete(_TAGS_PATH, json=_tag_bulk_payload(app_ids, tag_names))

    async def get_policy_in_use(self, tag_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified tags."""
        return await self._post(
            _TAGS_POLICY_IN_USE_PATH, json={"ids": id_strings(tag_ids, "tag_ids")}, retry_safe=True
        )


class PrivateAppsResource(SyncResource):
    """Synchronous interface to ``/api/v2/steering/apps/private``."""

    @functools.cached_property
    def with_response(self) -> PrivateAppResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._private_app_response import PrivateAppResponses

        return PrivateAppResponses(self._transport)

    @functools.cached_property
    def tags(self) -> PrivateAppTagsResource:
        """Access the private-app Tags API."""
        return PrivateAppTagsResource(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        app_name: str | None = None,
        publisher_name: str | None = None,
        reachable: bool | None = None,
        clientless_access: bool | None = None,
        host: str | None = None,
        in_policy: bool | None = None,
        protocol: str | None = None,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[PrivateApp]:
        """List all private applications.

        Every filter below is one term of the single ``query`` expression the
        endpoint takes (``npa_apps_private.yaml:490-524``); the terms are joined
        with ``and``, so ``app_name="dash", in_policy=True`` is sent as
        ``query=name sw dash and in_policy eq yes``.  Supply *query* (or
        *filter_expr*) to write the expression yourself; it leads, and the
        convenience filters are appended to it.

        Args:
            query: A filter expression, e.g. ``'name sw dash'``.  Operators and
                columns: ``npa_generic.yaml:495-504``.
            app_name: Applications whose name starts with this (``name sw``).
            publisher_name: Applications served by this publisher
                (``publisher_name eq``).
            reachable: Reachable or unreachable applications
                (``reachable eq yes|no``).
            clientless_access: Browser-access enabled or disabled
                (``clientless_access eq true|false``).
            host: Applications on this host (``host eq``).
            in_policy: Applications referenced by a policy, or not
                (``in_policy eq yes|no``).
            protocol: Browser-access protocol (``private_app_protocol eq``).
            filter_expr: A second expression, appended to *query* with ``and``.
            fields: Specific fields to include.
            page_size: Results per page.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(
                query,
                app_name,
                publisher_name,
                reachable,
                clientless_access,
                host,
                in_policy,
                protocol,
                filter_expr,
                fields,
            ),
            model=PrivateApp,
            page_size=page_size,
            extract=_extract,
        )

    def get(self, app_id: int) -> PrivateApp:
        """Get a private app by ID."""
        body = self._get(f"{_PATH}/{app_id}")
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def create(
        self,
        name: str,
        host: str,
        port: str | int,
        *,
        protocols: builtins.list[str | dict[str, Any]] | None = None,
        publisher_ids: builtins.list[int] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Create a new private application.

        The API pairs each transport with its port, so *port* and *protocols*
        become one ``protocols`` entry per protocol and *publisher_ids* are sent
        as strings.

        Args:
            name: Application name.
            host: Target host (IP or hostname).
            port: Target port or port range applied to every protocol, as a
                number or a string.
            protocols: Transports to expose (``["TCP"]``, ``["TCP", "UDP"]``,
                ``["TCP/UDP"]``), or ready-made ``{"type": ..., "port": ...}``
                entries.  Required — the API has nowhere else to carry *port*.
            publisher_ids: Publisher IDs to assign.
            extra_fields: Optional additional fields to include in the payload.

        Raises:
            netskope.exceptions.ValidationError: If *protocols* is missing or
                any field fails the create schema.
        """
        payload = _build_create_payload(name, host, port, protocols, publisher_ids, extra_fields)
        body = self._post(_PATH, json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def update(
        self,
        app_id: int,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Partially update a private application (``PATCH``).

        Only the provided fields are changed; everything else is preserved.

        Args:
            app_id: The application identifier.
            extra_fields: Fields to update.
        """
        body = self._patch(f"{_PATH}/{app_id}", json=extra_fields or {})
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def replace(self, app_id: int, payload: dict[str, Any]) -> PrivateApp:
        """Fully replace a private application (``PUT``).

        Args:
            app_id: The application identifier.
            payload: The complete application definition.
        """
        body = self._put(f"{_PATH}/{app_id}", json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def delete(self, app_id: int) -> None:
        """Delete a private application."""
        self._delete(f"{_PATH}/{app_id}")

    def bulk_delete(self, app_ids: builtins.list[int]) -> None:
        """Delete multiple private applications in one call.

        Args:
            app_ids: The identifiers of the applications to delete.
        """
        self._delete(_PATH, json={"private_app_ids": id_strings(app_ids, "app_ids")})

    def get_policy_in_use(self, app_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified applications."""
        return self._post(
            _POLICY_IN_USE_PATH, json={"ids": id_strings(app_ids, "app_ids")}, retry_safe=True
        )

    def get_discovery_settings(self) -> dict[str, Any]:
        """Get the private-app discovery settings."""
        return self._get(_DISCOVERY_PATH)

    def update_discovery_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Update the private-app discovery settings.

        Args:
            settings: The complete discovery-settings payload.
        """
        return self._post(_DISCOVERY_PATH, json=settings)

    def add_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> dict[str, Any]:
        """Add publisher associations to private applications."""
        return self._patch(_PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids))

    def replace_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> dict[str, Any]:
        """Replace all publisher associations on private applications."""
        return self._put(_PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids))

    def remove_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> None:
        """Remove publisher associations from private applications."""
        self._delete(_PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids))


class AsyncPrivateAppsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/steering/apps/private``."""

    @functools.cached_property
    def with_response(self) -> AsyncPrivateAppResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._private_app_response import AsyncPrivateAppResponses

        return AsyncPrivateAppResponses(self._transport)

    @functools.cached_property
    def tags(self) -> AsyncPrivateAppTagsResource:
        """Access the private-app Tags API."""
        return AsyncPrivateAppTagsResource(self._transport)

    def list(
        self,
        *,
        query: str | None = None,
        app_name: str | None = None,
        publisher_name: str | None = None,
        reachable: bool | None = None,
        clientless_access: bool | None = None,
        host: str | None = None,
        in_policy: bool | None = None,
        protocol: str | None = None,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[PrivateApp]:
        """List all private applications.

        See :meth:`PrivateAppsResource.list`.
        """
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(
                query,
                app_name,
                publisher_name,
                reachable,
                clientless_access,
                host,
                in_policy,
                protocol,
                filter_expr,
                fields,
            ),
            model=PrivateApp,
            page_size=page_size,
            extract=_extract,
        )

    async def get(self, app_id: int) -> PrivateApp:
        """Get a private app by ID."""
        body = await self._get(f"{_PATH}/{app_id}")
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def create(
        self,
        name: str,
        host: str,
        port: str | int,
        *,
        protocols: builtins.list[str | dict[str, Any]] | None = None,
        publisher_ids: builtins.list[int] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Create a new private application.

        See :meth:`PrivateAppsResource.create`.
        """
        payload = _build_create_payload(name, host, port, protocols, publisher_ids, extra_fields)
        body = await self._post(_PATH, json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def update(
        self,
        app_id: int,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Partially update a private application (``PATCH``)."""
        body = await self._patch(f"{_PATH}/{app_id}", json=extra_fields or {})
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def replace(self, app_id: int, payload: dict[str, Any]) -> PrivateApp:
        """Fully replace a private application (``PUT``)."""
        body = await self._put(f"{_PATH}/{app_id}", json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def delete(self, app_id: int) -> None:
        """Delete a private application."""
        await self._delete(f"{_PATH}/{app_id}")

    async def bulk_delete(self, app_ids: builtins.list[int]) -> None:
        """Delete multiple private applications in one call."""
        await self._delete(_PATH, json={"private_app_ids": id_strings(app_ids, "app_ids")})

    async def get_policy_in_use(self, app_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified applications."""
        return await self._post(
            _POLICY_IN_USE_PATH, json={"ids": id_strings(app_ids, "app_ids")}, retry_safe=True
        )

    async def get_discovery_settings(self) -> dict[str, Any]:
        """Get the private-app discovery settings."""
        return await self._get(_DISCOVERY_PATH)

    async def update_discovery_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Update the private-app discovery settings."""
        return await self._post(_DISCOVERY_PATH, json=settings)

    async def add_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> dict[str, Any]:
        """Add publisher associations to private applications."""
        return await self._patch(
            _PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids)
        )

    async def replace_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> dict[str, Any]:
        """Replace all publisher associations on private applications."""
        return await self._put(
            _PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids)
        )

    async def remove_publishers(
        self,
        app_ids: builtins.list[int],
        publisher_ids: builtins.list[int],
    ) -> None:
        """Remove publisher associations from private applications."""
        await self._delete(_PUBLISHERS_PATH, json=_publisher_assoc_payload(app_ids, publisher_ids))
