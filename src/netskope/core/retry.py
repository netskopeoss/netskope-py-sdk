"""Retry policy with exponential backoff and jitter.

The retry logic respects ``Retry-After`` headers from the server and applies
jitter to prevent thundering-herd effects across concurrent consumers.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx

from netskope.core.config import NetskopeConfig
from netskope.exceptions import ConnectionError, TimeoutError, parse_retry_after

logger = logging.getLogger("netskope")
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_RETRYABLE_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


def _sleep_duration(
    attempt: int,
    config: NetskopeConfig,
    retry_after: float | None,
) -> float:
    """Calculate how long to sleep before the next retry."""
    if retry_after is not None and retry_after > 0:
        return min(retry_after, 300.0)
    # Exponential backoff: factor * 2^attempt, capped at 60s, with jitter.
    base: float = config.backoff_factor * (2**attempt)
    capped: float = min(base, 60.0)
    jitter: float = random.uniform(0, capped * 0.1)
    return capped + jitter


def _should_retry(response: httpx.Response, config: NetskopeConfig) -> bool:
    return response.status_code in config.retry_on_status


def _get_retry_after(response: httpx.Response) -> float | None:
    return parse_retry_after(response.headers.get("retry-after"))


def _copy_request(request: httpx.Request) -> httpx.Request:
    """Create a fresh copy of a request so the stream can be re-read."""
    return httpx.Request(
        method=request.method,
        url=request.url,
        headers=request.headers,
        content=request.content,
        extensions=dict(request.extensions),
    )


def _retry_limit(request: httpx.Request, config: NetskopeConfig, retry_safe: bool | None) -> int:
    safe = request.method in _SAFE_METHODS if retry_safe is None else retry_safe
    if not safe:
        return 0
    try:
        _ = request.content
    except httpx.RequestNotRead:
        # Uploads and other streams may be single-use or too large to buffer.
        return 0
    return config.max_retries


def send_with_retries(
    client: httpx.Client,
    request: httpx.Request,
    config: NetskopeConfig,
    *,
    retry_safe: bool | None = None,
) -> httpx.Response:
    """Retry transient failures only for safe requests with replayable bodies."""
    retry_limit = _retry_limit(request, config, retry_safe)
    for attempt in range(retry_limit + 1):
        try:
            response = client.send(
                request if attempt == 0 else _copy_request(request),
                auth=None,
                follow_redirects=False,
            )
        except httpx.TransportError as exc:
            if attempt >= retry_limit or not isinstance(exc, _RETRYABLE_ERRORS):
                if isinstance(exc, httpx.TimeoutException):
                    raise TimeoutError(str(exc)) from exc
                raise ConnectionError(str(exc)) from exc
            sleep = _sleep_duration(attempt, config, None)
            logger.warning(
                "Netskope request failed (%s), retrying in %.1fs (attempt %d/%d)",
                exc,
                sleep,
                attempt + 1,
                retry_limit,
            )
            time.sleep(sleep)
            continue

        if not _should_retry(response, config) or attempt >= retry_limit:
            return response

        retry_after = _get_retry_after(response)
        sleep = _sleep_duration(attempt, config, retry_after)
        logger.warning(
            "Netskope API returned %d, retrying in %.1fs (attempt %d/%d)",
            response.status_code,
            sleep,
            attempt + 1,
            retry_limit,
        )
        response.close()
        time.sleep(sleep)

    raise RuntimeError("retry loop exited without a response")  # pragma: no cover


async def async_send_with_retries(
    client: httpx.AsyncClient,
    request: httpx.Request,
    config: NetskopeConfig,
    *,
    retry_safe: bool | None = None,
) -> httpx.Response:
    """Async variant of :func:`send_with_retries`."""
    retry_limit = _retry_limit(request, config, retry_safe)
    for attempt in range(retry_limit + 1):
        try:
            response = await client.send(
                request if attempt == 0 else _copy_request(request),
                auth=None,
                follow_redirects=False,
            )
        except httpx.TransportError as exc:
            if attempt >= retry_limit or not isinstance(exc, _RETRYABLE_ERRORS):
                if isinstance(exc, httpx.TimeoutException):
                    raise TimeoutError(str(exc)) from exc
                raise ConnectionError(str(exc)) from exc
            sleep = _sleep_duration(attempt, config, None)
            logger.warning(
                "Netskope request failed (%s), retrying in %.1fs (attempt %d/%d)",
                exc,
                sleep,
                attempt + 1,
                retry_limit,
            )
            await asyncio.sleep(sleep)
            continue

        if not _should_retry(response, config) or attempt >= retry_limit:
            return response

        retry_after = _get_retry_after(response)
        sleep = _sleep_duration(attempt, config, retry_after)
        logger.warning(
            "Netskope API returned %d, retrying in %.1fs (attempt %d/%d)",
            response.status_code,
            sleep,
            attempt + 1,
            retry_limit,
        )
        await response.aclose()
        await asyncio.sleep(sleep)

    raise RuntimeError("retry loop exited without a response")  # pragma: no cover
