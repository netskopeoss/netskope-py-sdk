"""Base resource class with shared helpers for sync and async resources."""

from __future__ import annotations

from typing import Any, cast

from netskope._transport import AsyncTransport, SyncTransport


class SyncResource:
    """Base class for synchronous resource namespaces."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = self._transport.request("GET", path, params=params or None)
        return cast(dict[str, Any], resp.json())

    def _post(self, path: str, *, json: Any = None, **params: Any) -> dict[str, Any]:
        resp = self._transport.request("POST", path, json=json, params=params or None)
        return cast(dict[str, Any], resp.json())

    def _put(self, path: str, *, json: Any = None) -> dict[str, Any]:
        resp = self._transport.request("PUT", path, json=json)
        return cast(dict[str, Any], resp.json())

    def _patch(self, path: str, *, json: Any = None) -> dict[str, Any]:
        resp = self._transport.request("PATCH", path, json=json)
        return cast(dict[str, Any], resp.json())

    def _delete(self, path: str) -> dict[str, Any]:
        resp = self._transport.request("DELETE", path)
        try:
            return cast(dict[str, Any], resp.json())
        except (ValueError, UnicodeDecodeError):
            return {}


class AsyncResource:
    """Base class for asynchronous resource namespaces."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        resp = await self._transport.request("GET", path, params=params or None)
        return cast(dict[str, Any], resp.json())

    async def _post(self, path: str, *, json: Any = None, **params: Any) -> dict[str, Any]:
        resp = await self._transport.request("POST", path, json=json, params=params or None)
        return cast(dict[str, Any], resp.json())

    async def _put(self, path: str, *, json: Any = None) -> dict[str, Any]:
        resp = await self._transport.request("PUT", path, json=json)
        return cast(dict[str, Any], resp.json())

    async def _patch(self, path: str, *, json: Any = None) -> dict[str, Any]:
        resp = await self._transport.request("PATCH", path, json=json)
        return cast(dict[str, Any], resp.json())

    async def _delete(self, path: str) -> dict[str, Any]:
        resp = await self._transport.request("DELETE", path)
        try:
            return cast(dict[str, Any], resp.json())
        except (ValueError, UnicodeDecodeError):
            return {}
