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

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from typing import Any

import httpx


class NetskopeError(Exception):
    """Base exception for every error raised by the Netskope SDK."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class APIError(NetskopeError):
    """The server returned an HTTP error or an API error envelope.

    Attributes:
        status_code: The HTTP status code (e.g. 400, 500).
        request_id: The server-assigned request identifier, useful for
            Netskope support escalation.
        body: The parsed JSON body, if available.
        request_method: The HTTP method of the failed request, if available.
        request_path: Its URL path without query parameters, if available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
        body: dict[str, Any] | None = None,
        request_method: str | None = None,
        request_path: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.request_id = request_id
        self.body = body
        self.request_method = request_method
        self.request_path = request_path
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
        request_method: str | None = None,
        request_path: str | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(
            message,
            status_code=status_code,
            request_id=request_id,
            body=body,
            request_method=request_method,
            request_path=request_path,
        )


class ServerError(APIError):
    """HTTP 5xx — a server-side failure on Netskope's end."""


class ValidationError(NetskopeError):
    """The request parameters failed client-side validation before sending."""


class ResponseValidationError(NetskopeError):
    """A successful response could not be parsed as the expected SDK type.

    ``field_errors`` contains only ``(location, error_type)`` pairs. Response
    values are excluded so an error can be displayed without exposing data.
    """

    def __init__(
        self,
        message: str,
        *,
        request_method: str | None = None,
        request_path: str | None = None,
        request_id: str | None = None,
        field_errors: tuple[tuple[tuple[str | int, ...], str], ...] = (),
    ) -> None:
        self.request_method = request_method
        self.request_path = request_path
        self.request_id = request_id
        self.field_errors = field_errors
        super().__init__(message)


class PaginationError(NetskopeError):
    """A response cannot support safe continuation of a paginated query."""

    def __init__(
        self,
        message: str,
        *,
        request_method: str | None = None,
        request_path: str | None = None,
        request_id: str | None = None,
        offset: int | None = None,
    ) -> None:
        self.request_method = request_method
        self.request_path = request_path
        self.request_id = request_id
        self.offset = offset
        super().__init__(message)


class ConnectionError(NetskopeError):
    """A network-level failure prevented the request from completing."""


class TimeoutError(NetskopeError):
    """The request did not complete within the configured timeout."""


class ClientClosedError(NetskopeError):
    """The SDK client was closed before this request was made."""


def parse_retry_after(raw: str | None) -> float | None:
    """Read a ``Retry-After`` header as seconds, per RFC 9110.

    Both forms are accepted: a delay in seconds and an HTTP date. Values in
    the past yield ``0.0``; anything unparsable, infinite, or NaN yields
    ``None``.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        pass
    else:
        return max(seconds, 0.0) if isfinite(seconds) else None
    try:
        deadline = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return max((deadline - datetime.now(UTC)).total_seconds(), 0.0)


_STATUS_MAP: dict[int, type[APIError]] = {
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
}


def _extract_message(body: dict[str, Any]) -> str:
    """Pull the most specific error message out of a Netskope error body."""
    raw: Any = body.get("status")
    raw = raw.get("message") if isinstance(raw, dict) else None
    if raw is None:
        raw = body.get("message")
    if raw is None:
        raw = body.get("error")
    if raw is None:
        result = body.get("result")
        if isinstance(result, str):
            raw = result
    if raw is None:
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            # FastAPI errors also contain input values and locations. Only the
            # server's messages belong in the user-facing exception.
            return "; ".join(
                item["msg"]
                for item in detail
                if isinstance(item, dict) and isinstance(item.get("msg"), str)
            )
    if isinstance(raw, list):
        return "; ".join(str(item) for item in raw)
    if isinstance(raw, dict):
        return str(raw.get("message", raw))
    if raw is not None:
        return str(raw)
    return ""


def _failed_execution_message(
    reported: str, request_method: str | None, request_path: str | None
) -> str:
    """Describe a datasearch query the service accepted and then failed."""
    endpoint = f" for {request_method} {request_path}" if request_method and request_path else ""
    message = f"The datasearch query reported execution=FAILED{endpoint}."
    return f"{message} {reported}" if reported else message


def raise_for_status(response: httpx.Response) -> None:
    """Inspect *response* and raise the appropriate :class:`APIError` subclass.

    This is called automatically by the transport layer; SDK users should
    never need to call it directly.

    Some Netskope endpoints return HTTP 200 with an error payload such as
    ``{"status": "error", "message": ...}`` — those are raised as errors too.
    """
    try:
        request_method = response.request.method
        request_path = response.request.url.path
    except RuntimeError:
        request_method = None
        request_path = None

    if response.is_success:
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(body, dict):
            return
        status = body.get("status")
        # Datasearch reports execution either inside the status envelope or
        # beside it, depending on the endpoint.
        status_envelope = status if isinstance(status, dict) else {}
        status_failed = status_envelope.get("execution") == "FAILED"
        failed_execution = status_failed or body.get("execution") == "FAILED"
        if (
            status == "error"
            or body.get("ok") == 0
            or body.get("success") is False
            or failed_execution
        ):
            reported = _extract_message(body)
            if failed_execution:
                # A bare "Unknown error" on an HTTP 200 tells the caller nothing
                # about which query failed, and these bodies often carry no
                # message at all.
                message = _failed_execution_message(reported, request_method, request_path)
            else:
                message = reported or "Unknown error"
            raw_status = (
                status_envelope.get("status_code") if status_failed else body.get("status_code")
            )
            status_code = (
                raw_status
                if isinstance(raw_status, int) and not isinstance(raw_status, bool)
                else response.status_code
            )
            request_id = response.headers.get("x-request-id")
            lowered = reported.lower()
            if (
                "not found" in lowered
                or "doesn't exist" in lowered
                or "does not exist" in lowered
                or ("no " in lowered and " found" in lowered)
            ):
                raise NotFoundError(
                    message,
                    status_code=status_code,
                    request_id=request_id,
                    body=body,
                    request_method=request_method,
                    request_path=request_path,
                )
            raise APIError(
                message,
                status_code=status_code,
                request_id=request_id,
                body=body,
                request_method=request_method,
                request_path=request_path,
            )
        return

    request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
    except (ValueError, UnicodeDecodeError):
        body = None

    message = _extract_message(body) if isinstance(body, dict) else ""
    if not message:
        message = response.reason_phrase or "Unknown error"

    status = response.status_code
    exc_cls = _STATUS_MAP.get(status)

    if exc_cls is RateLimitError:
        parsed_retry_after = parse_retry_after(response.headers.get("retry-after"))
        retry_after = None if parsed_retry_after is None else min(parsed_retry_after, 300.0)
        raise RateLimitError(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
            retry_after=retry_after,
            request_method=request_method,
            request_path=request_path,
        )

    if exc_cls is not None:
        raise exc_cls(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
            request_method=request_method,
            request_path=request_path,
        )

    if status >= 500:
        raise ServerError(
            str(message),
            status_code=status,
            request_id=request_id,
            body=body,
            request_method=request_method,
            request_path=request_path,
        )

    raise APIError(
        str(message),
        status_code=status,
        request_id=request_id,
        body=body,
        request_method=request_method,
        request_path=request_path,
    )
