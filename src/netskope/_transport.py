"""HTTP transport layer — the single point of contact with the network.

Provides both synchronous (:class:`SyncTransport`) and asynchronous
(:class:`AsyncTransport`) wrappers around :mod:`httpx`, with automatic
retries, token injection, request logging, and error mapping.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from netskope._config import NetskopeConfig
from netskope._retry import async_send_with_retries, send_with_retries
from netskope._version import __version__
from netskope.exceptions import raise_for_status

logger = logging.getLogger("netskope")

_USER_AGENT = f"netskope-python-sdk/{__version__}"


def _build_headers(config: NetskopeConfig) -> dict[str, str]:
    return {
        "Netskope-Api-Token": config.api_token.get_secret_value(),
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }


def _log_request(request: httpx.Request) -> None:
    logger.debug("→ %s %s", request.method, request.url)


def _log_response(response: httpx.Response) -> None:
    request_id = response.headers.get("x-request-id", "-")
    logger.debug(
        "← %s %s → %d (request_id=%s)",
        response.request.method,
        response.request.url.path,
        response.status_code,
        request_id,
    )


class SyncTransport:
    """Synchronous HTTP transport backed by :class:`httpx.Client`."""

    def __init__(self, config: NetskopeConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=_build_headers(config),
            timeout=httpx.Timeout(config.timeout),
            follow_redirects=False,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
    ) -> httpx.Response:
        """Send an HTTP request and return the validated response.

        Raises:
            netskope.exceptions.APIError: On any non-2xx response.
            netskope.exceptions.ConnectionError: On network failure.
            netskope.exceptions.TimeoutError: On request timeout.
        """
        request = self._client.build_request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
        )
        _log_request(request)
        response = send_with_retries(self._client, request, self._config)
        _log_response(response)
        raise_for_status(response)
        return response

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()


class AsyncTransport:
    """Asynchronous HTTP transport backed by :class:`httpx.AsyncClient`."""

    def __init__(self, config: NetskopeConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=_build_headers(config),
            timeout=httpx.Timeout(config.timeout),
            follow_redirects=False,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
    ) -> httpx.Response:
        """Send an async HTTP request and return the validated response."""
        request = self._client.build_request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
        )
        _log_request(request)
        response = await async_send_with_retries(self._client, request, self._config)
        _log_response(response)
        raise_for_status(response)
        return response

    async def close(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._client.aclose()
