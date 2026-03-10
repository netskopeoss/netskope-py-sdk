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
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.private_apps import PrivateApp
from netskope.resources._base import AsyncResource, SyncResource

_PATH = "/api/v2/steering/apps/private"


def _extract(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data", [])
    if isinstance(data, dict):
        apps = data.get("private_apps", [])
        if isinstance(apps, list):
            return apps
    if isinstance(data, list):
        return data
    return []


class PrivateAppsResource(SyncResource):
    """Synchronous interface to ``/api/v2/steering/apps/private``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[PrivateApp]:
        """List all private applications.

        Args:
            filter_expr: Optional filter expression.
            fields: Specific fields to include.
            page_size: Results per page.
        """
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        if fields:
            params["fields"] = ",".join(fields)
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
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
        body = self._post(_PATH, json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def update(
        self,
        app_id: int,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Update a private application.

        Args:
            app_id: The application identifier.
            extra_fields: Fields to update.
        """
        body = self._put(f"{_PATH}/{app_id}", json=extra_fields or {})
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    def delete(self, app_id: int) -> None:
        """Delete a private application."""
        self._delete(f"{_PATH}/{app_id}")


class AsyncPrivateAppsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/steering/apps/private``."""

    def list(
        self,
        *,
        filter_expr: str | None = None,
        fields: builtins.list[str] | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[PrivateApp]:
        """List all private applications."""
        params: dict[str, Any] = {}
        if filter_expr:
            params["filter"] = filter_expr
        if fields:
            params["fields"] = ",".join(fields)
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=params,
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
        body = await self._post(_PATH, json=payload)
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def update(
        self,
        app_id: int,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> PrivateApp:
        """Update a private application."""
        body = await self._put(f"{_PATH}/{app_id}", json=extra_fields or {})
        data = body.get("data", body)
        return PrivateApp.model_validate(data)

    async def delete(self, app_id: int) -> None:
        """Delete a private application."""
        await self._delete(f"{_PATH}/{app_id}")
