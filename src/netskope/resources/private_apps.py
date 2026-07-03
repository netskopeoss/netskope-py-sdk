"""Private Apps resource — manage ZTNA private applications.

Example::

    for app in client.private_apps.list():
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
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.private_apps import PrivateApp, PrivateAppTag
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list, validate_id

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
    params: dict[str, Any] = {}
    if query is not None:
        params["query"] = query
    if app_name is not None:
        params["app_name"] = app_name
    if publisher_name is not None:
        params["publisher_name"] = publisher_name
    if reachable is not None:
        params["reachable"] = reachable
    if clientless_access is not None:
        params["clientless_access"] = clientless_access
    if host is not None:
        params["host"] = host
    if in_policy is not None:
        params["in_policy"] = in_policy
    if protocol is not None:
        params["protocol"] = protocol
    if filter_expr:
        params["filter"] = filter_expr
    if fields:
        params["fields"] = ",".join(fields)
    return params


def _build_create_payload(
    name: str,
    host: str,
    port: str,
    protocols: builtins.list[str] | None,
    publisher_ids: builtins.list[int] | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "app_name": name,
        "host": host,
        "port": port,
    }
    if protocols is not None:
        payload["protocols"] = protocols
    if publisher_ids is not None:
        payload["publishers"] = [{"publisher_id": pid} for pid in publisher_ids]
    if extra_fields:
        payload.update(extra_fields)
    return payload


def _publisher_assoc_payload(
    app_ids: builtins.list[int],
    publisher_ids: builtins.list[int],
) -> dict[str, Any]:
    return {"private_app_ids": list(app_ids), "publisher_ids": list(publisher_ids)}


def _tag_objects(tag_names: builtins.list[str]) -> list[dict[str, str]]:
    return [{"tag_name": name} for name in tag_names]


def _tag_bulk_payload(
    app_ids: builtins.list[int | str],
    tag_names: builtins.list[str],
) -> dict[str, Any]:
    # The tags bulk endpoints expect app IDs as strings.
    return {"ids": [str(app_id) for app_id in app_ids], "tags": _tag_objects(tag_names)}


def _tag_create_payload(app_id: int | str, tag_names: builtins.list[str]) -> dict[str, Any]:
    # The tag create endpoint expects the app ID as a string.
    return {"id": str(app_id), "tags": _tag_objects(tag_names)}


class PrivateAppTagsResource(SyncResource):
    """Synchronous interface to ``/api/v2/steering/apps/private/tags``."""

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
        return self._post(_TAGS_POLICY_IN_USE_PATH, json={"ids": list(tag_ids)})


class AsyncPrivateAppTagsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/steering/apps/private/tags``."""

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
        return await self._post(_TAGS_POLICY_IN_USE_PATH, json={"ids": list(tag_ids)})


class PrivateAppsResource(SyncResource):
    """Synchronous interface to ``/api/v2/steering/apps/private``."""

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

        Args:
            query: Search query string to filter applications.
            app_name: Filter by application name.
            publisher_name: Filter by publisher name.
            reachable: Filter by reachability status.
            clientless_access: Filter by clientless access enabled/disabled.
            host: Filter by host name.
            in_policy: Filter by whether the app is in a policy.
            protocol: Filter by protocol (e.g. ``"tcp"``, ``"udp"``).
            filter_expr: Optional filter expression.
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
        port: str,
        *,
        protocols: builtins.list[str] | None = None,
        publisher_ids: builtins.list[int] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Create a new private application.

        Args:
            name: Application name.
            host: Target host (IP or hostname).
            port: Target port(s).
            protocols: List of protocols (``["TCP"]``, ``["UDP"]``, etc.).
            publisher_ids: Publisher IDs to assign.
            extra_fields: Optional additional fields to include in the payload.
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
        self._delete(_PATH, json={"private_app_ids": list(app_ids)})

    def get_policy_in_use(self, app_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified applications."""
        return self._post(_POLICY_IN_USE_PATH, json={"ids": list(app_ids)})

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
        port: str,
        *,
        protocols: builtins.list[str] | None = None,
        publisher_ids: builtins.list[int] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Create a new private application."""
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
        await self._delete(_PATH, json={"private_app_ids": list(app_ids)})

    async def get_policy_in_use(self, app_ids: builtins.list[int]) -> dict[str, Any]:
        """Check which policies reference the specified applications."""
        return await self._post(_POLICY_IN_USE_PATH, json={"ids": list(app_ids)})

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
