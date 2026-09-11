"""HTTP transport layer — the single point of contact with the network.

Provides both synchronous (:class:`SyncTransport`) and asynchronous
(:class:`AsyncTransport`) wrappers around :mod:`httpx`, with automatic
retries, token injection, request logging, and error mapping.
"""

from __future__ import annotations

import logging
import ssl
from typing import Any

import httpx

from netskope._config import NetskopeConfig
from netskope._retry import async_send_with_retries, send_with_retries
from netskope._version import __version__
from netskope.exceptions import ClientClosedError, ValidationError, raise_for_status

logger = logging.getLogger("netskope")

_USER_AGENT = f"netskope-python-sdk/{__version__}"


def _build_headers(config: NetskopeConfig) -> dict[str, str]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }
    if config.api_token is not None:
        headers["Netskope-Api-Token"] = config.api_token.get_secret_value()
    return headers


def _build_request(
    config: NetskopeConfig,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None,
    json: Any | None,
    data: Any | None,
    files: Any | None,
) -> httpx.Request:
    try:
        base_url = httpx.URL(config.base_url)
        url = base_url.join(path)
    except httpx.InvalidURL as exc:
        raise ValidationError("Invalid Netskope request URL.") from exc
    if (url.scheme, url.host, url.port) != (base_url.scheme, base_url.host, base_url.port):
        raise ValidationError("Requests must target the configured Netskope tenant.")
    if url.userinfo:
        raise ValidationError("Request URLs must not contain credentials.")

    # Build independently of borrowed clients so their credentials, cookies,
    # query defaults, and base URL cannot enter a Netskope request.
    request = httpx.Request(
        method,
        url,
        headers=_build_headers(config),
        params=params,
        json=json,
        data=data,
        files=files,
        extensions={"timeout": httpx.Timeout(config.timeout).as_dict()},
    )
    if config.ci_session is not None:
        httpx.Cookies({"ci_session": config.ci_session.get_secret_value()}).set_cookie_header(
            request
        )
    return request


def _resolve_verify(config: NetskopeConfig) -> bool | ssl.SSLContext:
    """Translate ``config.verify`` into a value httpx accepts.

    A CA bundle path is turned into an :class:`ssl.SSLContext` so it is
    loaded once and shared by the connection pool.
    """
    if isinstance(config.verify, str):
        return ssl.create_default_context(cafile=config.verify)
    return config.verify


def _log_request(request: httpx.Request) -> None:
    logger.debug("→ %s %s", request.method, request.url.path)


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

    def __init__(self, config: NetskopeConfig, *, http_client: httpx.Client | None = None) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._closed = False
        self._client = (
            http_client
            if http_client is not None
            else httpx.Client(
                timeout=httpx.Timeout(config.timeout),
                follow_redirects=False,
                verify=_resolve_verify(config),
            )
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
        retry_safe: bool | None = None,
    ) -> httpx.Response:
        """Send an HTTP request and return the validated response.

        ``retry_safe`` overrides the GET/HEAD/OPTIONS retry default. Requests
        with streaming bodies are sent once even when marked safe.

        Raises:
            netskope.exceptions.APIError: On any non-2xx response.
            netskope.exceptions.ConnectionError: On network failure.
            netskope.exceptions.TimeoutError: On request timeout.
        """
        if self._closed:
            raise ClientClosedError("The Netskope client is closed.")
        request = _build_request(
            self._config,
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
        )
        _log_request(request)
        response = send_with_retries(self._client, request, self._config, retry_safe=retry_safe)
        _log_response(response)
        raise_for_status(response)
        return response

    @property
    def closed(self) -> bool:
        """Whether this transport has been closed."""
        return self._closed

    def close(self) -> None:
        """Close this transport and its connection pool, if owned."""
        if not self._closed:
            self._closed = True
            if self._owns_client:
                self._client.close()


class AsyncTransport:
    """Asynchronous HTTP transport backed by :class:`httpx.AsyncClient`."""

    def __init__(
        self, config: NetskopeConfig, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._closed = False
        self._client = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(
                timeout=httpx.Timeout(config.timeout),
                follow_redirects=False,
                verify=_resolve_verify(config),
            )
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
        retry_safe: bool | None = None,
    ) -> httpx.Response:
        """Send an async HTTP request and return the validated response."""
        if self._closed:
            raise ClientClosedError("The Netskope client is closed.")
        request = _build_request(
            self._config,
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
        )
        _log_request(request)
        response = await async_send_with_retries(
            self._client, request, self._config, retry_safe=retry_safe
        )
        _log_response(response)
        raise_for_status(response)
        return response

    @property
    def closed(self) -> bool:
        """Whether this transport has been closed."""
        return self._closed

    async def close(self) -> None:
        """Close this transport and its connection pool, if owned."""
        if not self._closed:
            self._closed = True
            if self._owns_client:
                await self._client.aclose()
