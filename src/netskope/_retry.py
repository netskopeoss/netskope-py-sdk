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

from netskope._config import NetskopeConfig

logger = logging.getLogger("netskope")


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
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def send_with_retries(
    client: httpx.Client,
    request: httpx.Request,
    config: NetskopeConfig,
) -> httpx.Response:
    """Send *request* through *client*, retrying on transient failures."""
    last_response: httpx.Response | None = None
    for attempt in range(config.max_retries + 1):
        try:
            response = client.send(request)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            if attempt >= config.max_retries:
                from netskope.exceptions import ConnectionError, TimeoutError

                if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
                    raise TimeoutError(str(exc)) from exc
                raise ConnectionError(str(exc)) from exc
            sleep = _sleep_duration(attempt, config, None)
            logger.warning(
                "Netskope request failed (%s), retrying in %.1fs (attempt %d/%d)",
                exc,
                sleep,
                attempt + 1,
                config.max_retries,
            )
            time.sleep(sleep)
            continue

        if not _should_retry(response, config) or attempt >= config.max_retries:
            return response

        last_response = response
        retry_after = _get_retry_after(response)
        sleep = _sleep_duration(attempt, config, retry_after)
        logger.warning(
            "Netskope API returned %d, retrying in %.1fs (attempt %d/%d)",
            response.status_code,
            sleep,
            attempt + 1,
            config.max_retries,
        )
        time.sleep(sleep)

    # Should be unreachable, but satisfy the type checker.
    if last_response is None:  # pragma: no cover
        raise RuntimeError("retry loop exited without a response")
    return last_response


async def async_send_with_retries(
    client: httpx.AsyncClient,
    request: httpx.Request,
    config: NetskopeConfig,
) -> httpx.Response:
    """Async variant of :func:`send_with_retries`."""
    last_response: httpx.Response | None = None
    for attempt in range(config.max_retries + 1):
        try:
            response = await client.send(request)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            if attempt >= config.max_retries:
                from netskope.exceptions import ConnectionError, TimeoutError

                if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
                    raise TimeoutError(str(exc)) from exc
                raise ConnectionError(str(exc)) from exc
            sleep = _sleep_duration(attempt, config, None)
            logger.warning(
                "Netskope request failed (%s), retrying in %.1fs (attempt %d/%d)",
                exc,
                sleep,
                attempt + 1,
                config.max_retries,
            )
            await asyncio.sleep(sleep)
            continue

        if not _should_retry(response, config) or attempt >= config.max_retries:
            return response

        last_response = response
        retry_after = _get_retry_after(response)
        sleep = _sleep_duration(attempt, config, retry_after)
        logger.warning(
            "Netskope API returned %d, retrying in %.1fs (attempt %d/%d)",
            response.status_code,
            sleep,
            attempt + 1,
            config.max_retries,
        )
        await asyncio.sleep(sleep)

    assert last_response is not None
    return last_response
