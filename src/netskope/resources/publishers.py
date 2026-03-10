"""Publishers resource — manage private-access gateway publishers.

Example::

    for pub in client.publishers.list():
        print(f"{pub.publisher_name} — status={pub.status}")

    new_pub = client.publishers.create(name="aws-us-east-1")
"""

from __future__ import annotations

from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.publishers import Publisher
from netskope.resources._base import AsyncResource, SyncResource

_PATH = "/api/v2/infrastructure/publishers"


def _extract(body: dict[str, Any]) -> list[dict[str, Any]]:
    data = body.get("data", [])
    if isinstance(data, dict):
        publishers = data.get("publishers", [])
        if isinstance(publishers, list):
            return publishers
    if isinstance(data, list):
        return data
    return []


class PublishersResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/publishers``."""

    def list(self, *, page_size: int = 100) -> SyncPaginatedResponse[Publisher]:
        """List all publishers with automatic pagination.

        Returns:
            A lazy paginated iterator of
            :class:`~netskope.models.publishers.Publisher`.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params={},
            model=Publisher,
            page_size=page_size,
            extract=_extract,
        )

    def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID.

        Args:
            publisher_id: The numeric publisher identifier.
        """
        body = self._get(f"{_PATH}/{publisher_id}")
        data = body.get("data", body)
        if isinstance(data, dict) and "publishers" in data:
            items = data["publishers"]
            if items:
                return Publisher.model_validate(items[0])
        return Publisher.model_validate(data)

    def create(
        self,
        name: str,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Register a new publisher.

        Args:
            name: Human-readable publisher name.
            extra_fields: Optional additional publisher settings.
        """
        payload: dict[str, Any] = {"publisher_name": name}
        if extra_fields:
            payload.update(extra_fields)
        body = self._post(_PATH, json=payload)
        data = body.get("data", body)
        return Publisher.model_validate(data)

    def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Update a publisher.

        Args:
            publisher_id: The publisher identifier.
            name: New name (optional).
            extra_fields: Optional additional settings to update.
        """
        payload: dict[str, Any] = {}
        if name is not None:
            payload["publisher_name"] = name
        if extra_fields:
            payload.update(extra_fields)
        body = self._put(f"{_PATH}/{publisher_id}", json=payload)
        data = body.get("data", body)
        return Publisher.model_validate(data)

    def delete(self, publisher_id: int) -> None:
        """Delete a publisher.

        Args:
            publisher_id: The publisher identifier.
        """
        self._delete(f"{_PATH}/{publisher_id}")


class AsyncPublishersResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/publishers``."""

    def list(self, *, page_size: int = 100) -> AsyncPaginatedResponse[Publisher]:
        """List all publishers with automatic pagination."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params={},
            model=Publisher,
            page_size=page_size,
            extract=_extract,
        )

    async def get(self, publisher_id: int) -> Publisher:
        """Get a publisher by ID."""
        body = await self._get(f"{_PATH}/{publisher_id}")
        data = body.get("data", body)
        if isinstance(data, dict) and "publishers" in data:
            items = data["publishers"]
            if items:
                return Publisher.model_validate(items[0])
        return Publisher.model_validate(data)

    async def create(
        self,
        name: str,
        *,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Register a new publisher."""
        payload: dict[str, Any] = {"publisher_name": name}
        if extra_fields:
            payload.update(extra_fields)
        body = await self._post(_PATH, json=payload)
        data = body.get("data", body)
        return Publisher.model_validate(data)

    async def update(
        self,
        publisher_id: int,
        *,
        name: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> Publisher:
        """Update a publisher."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["publisher_name"] = name
        if extra_fields:
            payload.update(extra_fields)
        body = await self._put(f"{_PATH}/{publisher_id}", json=payload)
        data = body.get("data", body)
        return Publisher.model_validate(data)

    async def delete(self, publisher_id: int) -> None:
        """Delete a publisher."""
        await self._delete(f"{_PATH}/{publisher_id}")
