"""Opt-in access to a completed response and its typed interpretation."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

import httpx
from pydantic import ValidationError as PydanticValidationError

from netskope.exceptions import NetskopeError, ResponseValidationError

T = TypeVar("T")
_UNPARSED = object()


class ApiResponse(Generic[T]):
    """A buffered HTTP response with lazy, cached typed parsing.

    Inspecting or parsing this object never sends another request. Original
    response content remains available when validation fails.
    """

    def __init__(self, response: httpx.Response, parser: Callable[[httpx.Response], T]) -> None:
        self._response = response
        self._parser = parser
        self._parsed: T | object = _UNPARSED

    @property
    def status_code(self) -> int:
        """The HTTP status code of the buffered response."""
        return self._response.status_code

    @property
    def headers(self) -> httpx.Headers:
        """A copy of the response headers, safe to mutate without affecting parsing."""
        return self._response.headers.copy()

    @property
    def content(self) -> bytes:
        """The raw response body as bytes, still available after a failed parse."""
        return self._response.content

    @property
    def request_id(self) -> str | None:
        """The tenant's ``x-request-id`` header, or ``None`` when it was not sent."""
        return cast(str | None, self._response.headers.get("x-request-id"))

    @property
    def request_method(self) -> str | None:
        """The HTTP method that produced this response, or ``None`` if unrecorded."""
        try:
            return self._response.request.method
        except RuntimeError:
            return None

    @property
    def request_path(self) -> str | None:
        """The request URL path, or ``None`` if the response carries no request."""
        try:
            return self._response.request.url.path
        except RuntimeError:
            return None

    def json(self) -> Any:
        """Decode the original JSON independently of the typed result."""
        return self._response.json()

    def _add_request_context(self, error: NetskopeError) -> None:
        """Supply the request context a decoder has no access to."""
        for name, value in (
            ("request_method", self.request_method),
            ("request_path", self.request_path),
            ("request_id", self.request_id),
        ):
            if value is not None and hasattr(error, name) and getattr(error, name) is None:
                setattr(error, name, value)

    def parse(self) -> T:
        """Return the typed result, without exposing response values in errors."""
        if self._parsed is _UNPARSED:
            try:
                self._parsed = self._parser(self._response)
            except PydanticValidationError as exc:
                field_errors = tuple((tuple(error["loc"]), error["type"]) for error in exc.errors())
                raise ResponseValidationError(
                    "The API response does not match the expected schema.",
                    request_method=self.request_method,
                    request_path=self.request_path,
                    request_id=self.request_id,
                    field_errors=field_errors,
                ) from None
            except NetskopeError as exc:
                # Decoders raise the diagnostic they can state precisely; only
                # the request context is missing here.
                self._add_request_context(exc)
                raise
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Codec and JSON errors quote the body around a byte position.
                raise ResponseValidationError(
                    "The API response body is not valid JSON.",
                    request_method=self.request_method,
                    request_path=self.request_path,
                    request_id=self.request_id,
                ) from None
            except ValueError as exc:
                raise ResponseValidationError(
                    f"The API response could not be decoded: {exc}",
                    request_method=self.request_method,
                    request_path=self.request_path,
                    request_id=self.request_id,
                ) from exc
        return cast(T, self._parsed)

    def __repr__(self) -> str:
        return (
            f"ApiResponse(status_code={self.status_code}, parsed={self._parsed is not _UNPARSED})"
        )
