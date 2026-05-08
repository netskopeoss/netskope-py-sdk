"""URL Lists resource — manage URL allow/block lists and deploy policy.

Example::

    # List all URL lists
    for url_list in client.url_lists.list():
        print(f"{url_list.name}: {len(url_list.urls)} entries")

    # Create a new blocklist
    new_list = client.url_lists.create(
        name="threat-iocs",
        urls=["malware.example.com", "phishing.bad.org"],
        list_type="exact",
    )

    # Deploy all pending changes
    client.url_lists.deploy()
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.models.url_lists import UrlList
from netskope.resources._base import AsyncResource, SyncResource

_PATH = "/api/v2/policy/urllist"
_DEPLOY_PATH = "/api/v2/policy/deploy"


def _flatten_url_list(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested 'data' key into the top-level item dict."""
    if "data" in item and isinstance(item["data"], dict):
        flat = {**item}
        inner = flat.pop("data")
        flat.update(inner)
        return flat
    return item


def _extract(body: Any) -> list[dict[str, Any]]:
    """Extract URL list items, handling both list and dict envelopes."""
    items: list[dict[str, Any]] = []
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        data = body.get("data", [])
        if isinstance(data, dict):
            urllists = data.get("urllists", [])
            items = urllists if isinstance(urllists, list) else [data]
        elif isinstance(data, list):
            items = data
    return [_flatten_url_list(item) for item in items if isinstance(item, dict)]


def _extract_one(body: Any) -> dict[str, Any]:
    """Extract a single URL list item from any of the response shapes the API returns.

    POST returns ``[{...}]`` while GET/PUT return ``{...}``. The item itself wraps
    ``urls``/``type`` under a nested ``data`` key, which :func:`_flatten_url_list`
    merges into the top level so the model receives the fields it expects.
    """
    if isinstance(body, list):
        item = body[0] if body and isinstance(body[0], dict) else {}
    elif isinstance(body, dict):
        item = body
    else:
        item = {}
    return _flatten_url_list(item)


def _build_payload(name: str, urls: builtins.list[str], list_type: str) -> dict[str, Any]:
    """Build the request body the API requires: name at top, urls/type wrapped in ``data``."""
    return {"name": name, "data": {"urls": urls, "type": list_type}}


class UrlListsResource(SyncResource):
    """Synchronous interface to ``/api/v2/policy/urllist``."""

    def list(self, *, page_size: int = 100) -> SyncPaginatedResponse[UrlList]:
        """List all URL lists with automatic pagination.

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.url_lists.UrlList`.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params={},
            model=UrlList,
            page_size=page_size,
            extract=_extract,
        )

    def get(self, list_id: int) -> UrlList:
        """Get a URL list by ID.

        Args:
            list_id: The numeric URL list identifier.

        Returns:
            A :class:`~netskope.models.url_lists.UrlList` instance.
        """
        body = self._get(f"{_PATH}/{list_id}")
        return UrlList.model_validate(_extract_one(body))

    def create(
        self,
        name: str,
        urls: builtins.list[str],
        *,
        list_type: str = "exact",
    ) -> UrlList:
        """Create a new URL list.

        Args:
            name: Human-readable name for the list.
            urls: The URLs to include.
            list_type: Matching strategy (``"exact"`` or ``"regex"``).

        Returns:
            The newly created :class:`~netskope.models.url_lists.UrlList`.
        """
        body = self._post(_PATH, json=_build_payload(name, urls, list_type))
        return UrlList.model_validate(_extract_one(body))

    def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: builtins.list[str] | None = None,
        list_type: str | None = None,
    ) -> UrlList:
        """Update an existing URL list.

        The Netskope API requires ``name``, ``data.urls``, and ``data.type`` on every
        PUT request, so this method GETs the current list first and merges the provided
        fields over the existing values. Callers only need to supply what they want to
        change. At least one of ``name``, ``urls``, or ``list_type`` must be provided.

        Args:
            list_id: The URL list identifier.
            name: New name (optional).
            urls: New URL entries (optional).
            list_type: New matching strategy (optional).

        Returns:
            The updated :class:`~netskope.models.url_lists.UrlList`.
        """
        if name is None and urls is None and list_type is None:
            raise ValueError("update() requires at least one of name, urls, or list_type")
        current = self.get(list_id)
        merged_name = name if name is not None else (current.name or "")
        merged_urls = urls if urls is not None else list(current.urls)
        merged_type = list_type if list_type is not None else (current.type or "exact")
        body = self._put(
            f"{_PATH}/{list_id}",
            json=_build_payload(merged_name, merged_urls, merged_type),
        )
        return UrlList.model_validate(_extract_one(body))

    def delete(self, list_id: int) -> None:
        """Delete a URL list.

        Args:
            list_id: The URL list identifier.
        """
        self._delete(f"{_PATH}/{list_id}")

    def deploy(self) -> dict[str, Any]:
        """Deploy all pending policy changes.

        Returns:
            The deployment status from the API.
        """
        return self._post(_DEPLOY_PATH)


class AsyncUrlListsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/policy/urllist``."""

    def list(self, *, page_size: int = 100) -> AsyncPaginatedResponse[UrlList]:
        """List all URL lists with automatic pagination."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params={},
            model=UrlList,
            page_size=page_size,
            extract=_extract,
        )

    async def get(self, list_id: int) -> UrlList:
        """Get a URL list by ID."""
        body = await self._get(f"{_PATH}/{list_id}")
        return UrlList.model_validate(_extract_one(body))

    async def create(
        self,
        name: str,
        urls: builtins.list[str],
        *,
        list_type: str = "exact",
    ) -> UrlList:
        """Create a new URL list."""
        body = await self._post(_PATH, json=_build_payload(name, urls, list_type))
        return UrlList.model_validate(_extract_one(body))

    async def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: builtins.list[str] | None = None,
        list_type: str | None = None,
    ) -> UrlList:
        """Update an existing URL list.

        The API requires ``name``, ``data.urls``, and ``data.type`` on every PUT, so
        this method GETs the current list first and merges the provided fields over
        the existing values. At least one of ``name``, ``urls``, or ``list_type`` must
        be provided.
        """
        if name is None and urls is None and list_type is None:
            raise ValueError("update() requires at least one of name, urls, or list_type")
        current = await self.get(list_id)
        merged_name = name if name is not None else (current.name or "")
        merged_urls = urls if urls is not None else list(current.urls)
        merged_type = list_type if list_type is not None else (current.type or "exact")
        body = await self._put(
            f"{_PATH}/{list_id}",
            json=_build_payload(merged_name, merged_urls, merged_type),
        )
        return UrlList.model_validate(_extract_one(body))

    async def delete(self, list_id: int) -> None:
        """Delete a URL list."""
        await self._delete(f"{_PATH}/{list_id}")

    async def deploy(self) -> dict[str, Any]:
        """Deploy all pending policy changes."""
        return await self._post(_DEPLOY_PATH)
