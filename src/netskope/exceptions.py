"""Exception hierarchy for the Netskope SDK.

All exceptions inherit from :class:`NetskopeError`, enabling callers to catch
everything with a single ``except NetskopeError`` or handle specific failure
modes with more specific types.

Example::

    from netskope.exceptions import NotFoundError, RateLimitError

    try:
        alert = client.alerts.get("nonexistent")
    except NotFoundError as exc:
        print(f"Not found — request_id={exc.request_id}")
    except RateLimitError as exc:
        print(f"Rate-limited — retry after {exc.retry_after}s")
"""

from __future__ import annotations

from typing import Any

import httpx


class NetskopeError(Exception):
    """Base exception for every error raised by the Netskope SDK."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class APIError(NetskopeError):
    """An HTTP response with a non-2xx status code was received.

    Attributes:
        status_code: The HTTP status code (e.g. 400, 500).
        request_id: The server-assigned request identifier, useful for
            Netskope support escalation.
        body: The parsed JSON body, if available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.request_id = request_id
        self.body = body
        detail = f"[HTTP {status_code}]"
        if request_id:
            detail += f" request_id={request_id}"
        detail += f" {message}"
        super().__init__(detail)


class AuthenticationError(APIError):
    """HTTP 401 — the API token is invalid, expired, or missing."""


class ForbiddenError(APIError):
    """HTTP 403 — the token lacks the required scope for this operation."""


class NotFoundError(APIError):
    """HTTP 404 — the requested resource does not exist."""


class ConflictError(APIError):
    """HTTP 409 — a resource conflict occurred (e.g. duplicate name)."""


class RateLimitError(APIError):
    """HTTP 429 — the tenant rate limit has been exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, parsed from the
            ``Retry-After`` response header (``None`` if absent).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        request_id: str | None = None,
        body: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(
            message,
            status_code=status_code,
            request_id=request_id,
            body=body,
        )


class ServerError(APIError):
    """HTTP 5xx — a server-side failure on Netskope's end."""


class ValidationError(NetskopeError):
    """The request parameters failed client-side validation before sending."""


class ConnectionError(NetskopeError):
    """A network-level failure prevented the request from completing."""


class TimeoutError(NetskopeError):
    """The request did not complete within the configured timeout."""


_STATUS_MAP: dict[int, type[APIError]] = {
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
}


def raise_for_status(response: httpx.Response) -> None:
    """Inspect *response* and raise the appropriate :class:`APIError` subclass.

    This is called automatically by the transport layer; SDK users should
    never need to call it directly.
    """
    if response.is_success:
        return

    request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
    except (ValueError, UnicodeDecodeError):
        body = None

    message = ""
    if body and isinstance(body, dict):
        message = body.get("message", body.get("error", ""))
        if isinstance(message, dict):
            message = message.get("message", str(message))
    if not message:
        message = response.reason_phrase or "Unknown error"

    status = response.status_code
    exc_cls = _STATUS_MAP.get(status)

    if exc_cls is RateLimitError:
        retry_after_raw = response.headers.get("retry-after")
        try:
            retry_after = min(float(retry_after_raw), 300.0) if retry_after_raw else None
        except (ValueError, TypeError):
            retry_after = None
        raise RateLimitError(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
            retry_after=retry_after,
        )

    if exc_cls is not None:
        raise exc_cls(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
        )

    if status >= 500:
        raise ServerError(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
        )

    raise APIError(
        str(message),
        status_code=status,
        request_id=request_id,
        body=body,
    )
