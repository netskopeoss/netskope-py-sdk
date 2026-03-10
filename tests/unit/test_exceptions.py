"""Tests for the exception hierarchy."""

from __future__ import annotations

import httpx
import pytest

from netskope.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NetskopeError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    raise_for_status,
)


class TestExceptionHierarchy:
    """Verify the inheritance chain."""

    def test_all_inherit_from_netskope_error(self) -> None:
        assert issubclass(APIError, NetskopeError)
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(ForbiddenError, APIError)
        assert issubclass(NotFoundError, APIError)
        assert issubclass(ConflictError, APIError)
        assert issubclass(RateLimitError, APIError)
        assert issubclass(ServerError, APIError)
        assert issubclass(ValidationError, NetskopeError)

    def test_api_error_attributes(self) -> None:
        err = APIError(
            "bad request",
            status_code=400,
            request_id="req-123",
            body={"error": "invalid"},
        )
        assert err.status_code == 400
        assert err.request_id == "req-123"
        assert err.body == {"error": "invalid"}
        assert "400" in str(err)
        assert "req-123" in str(err)

    def test_rate_limit_error_retry_after(self) -> None:
        err = RateLimitError("slow down", retry_after=30.0)
        assert err.retry_after == 30.0
        assert err.status_code == 429


class TestRaiseForStatus:
    """Tests for the raise_for_status helper."""

    def _make_response(
        self,
        status: int,
        json_body: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        resp = httpx.Response(
            status,
            json=json_body or {},
            headers=headers or {},
            request=httpx.Request("GET", "https://test.goskope.com/api/v2/test"),
        )
        return resp

    def test_success_does_nothing(self) -> None:
        resp = self._make_response(200)
        raise_for_status(resp)  # Should not raise

    def test_401_raises_authentication_error(self) -> None:
        resp = self._make_response(401, {"message": "Invalid token"})
        with pytest.raises(AuthenticationError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.status_code == 401

    def test_403_raises_permission_error(self) -> None:
        resp = self._make_response(403, {"message": "Forbidden"})
        with pytest.raises(ForbiddenError):
            raise_for_status(resp)

    def test_404_raises_not_found_error(self) -> None:
        resp = self._make_response(404, {"message": "Not found"})
        with pytest.raises(NotFoundError):
            raise_for_status(resp)

    def test_409_raises_conflict_error(self) -> None:
        resp = self._make_response(409, {"message": "Conflict"})
        with pytest.raises(ConflictError):
            raise_for_status(resp)

    def test_429_raises_rate_limit_error_with_retry_after(self) -> None:
        resp = self._make_response(
            429,
            {"message": "Rate limited"},
            headers={"retry-after": "60"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.retry_after == 60.0

    def test_500_raises_server_error(self) -> None:
        resp = self._make_response(500, {"message": "Internal error"})
        with pytest.raises(ServerError):
            raise_for_status(resp)

    def test_502_raises_server_error(self) -> None:
        resp = self._make_response(502, {"message": "Bad gateway"})
        with pytest.raises(ServerError):
            raise_for_status(resp)

    def test_unknown_4xx_raises_api_error(self) -> None:
        resp = self._make_response(418, {"message": "I'm a teapot"})
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.status_code == 418

    def test_request_id_from_header(self) -> None:
        resp = self._make_response(
            500,
            {"message": "Error"},
            headers={"x-request-id": "req-abc"},
        )
        with pytest.raises(ServerError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.request_id == "req-abc"

    def test_nested_error_message(self) -> None:
        resp = self._make_response(400, {"error": {"message": "Nested error"}})
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert "Nested error" in str(exc_info.value)
