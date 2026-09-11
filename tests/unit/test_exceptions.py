"""Tests for the exception hierarchy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

import netskope
from netskope.exceptions import (
    APIError,
    AuthenticationError,
    ClientClosedError,
    ConflictError,
    ForbiddenError,
    NetskopeError,
    NotFoundError,
    PaginationError,
    RateLimitError,
    ResponseValidationError,
    ServerError,
    ValidationError,
    parse_retry_after,
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
        assert issubclass(ResponseValidationError, NetskopeError)
        assert issubclass(PaginationError, NetskopeError)
        assert issubclass(ClientClosedError, NetskopeError)

    def test_client_closed_error_is_exported_at_the_top_level(self) -> None:
        assert netskope.ClientClosedError is ClientClosedError
        assert "ClientClosedError" in netskope.__all__

    def test_pagination_error_context(self) -> None:
        err = PaginationError(
            "The API repeated a page.",
            request_method="POST",
            request_path="/api/v2/devices/device/tags/gettags",
            request_id="req-123",
            offset=100,
        )
        assert err.request_method == "POST"
        assert err.request_path == "/api/v2/devices/device/tags/gettags"
        assert err.request_id == "req-123"
        assert err.offset == 100
        assert str(err) == "The API repeated a page."

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

    def test_response_validation_error_context(self) -> None:
        err = ResponseValidationError(
            "The API response did not match Publisher.",
            request_method="POST",
            request_path="/api/v2/infrastructure/publishers",
            request_id="req-123",
            field_errors=((("data", 0, "publisher_id"), "int_parsing"),),
        )
        assert err.request_method == "POST"
        assert err.request_path == "/api/v2/infrastructure/publishers"
        assert err.request_id == "req-123"
        assert err.field_errors == ((("data", 0, "publisher_id"), "int_parsing"),)
        assert str(err) == "The API response did not match Publisher."


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

    @pytest.mark.parametrize(
        ("detail", "expected"),
        [
            ("Query rejected", "Query rejected"),
            (
                [{"msg": "Cannot find function 'count_distinct'", "input": "secret"}],
                "Cannot find function 'count_distinct'",
            ),
            ([{"msg": "First"}, None, {"msg": 42}, {"msg": "Second"}], "First; Second"),
        ],
    )
    def test_fastapi_detail_message(self, detail: object, expected: str) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(422, {"detail": detail}))
        assert expected in str(caught.value)
        assert "secret" not in str(caught.value)

    def test_fastapi_detail_does_not_override_message(self) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(
                self._make_response(422, {"message": "Preferred", "detail": "Ignored"})
            )
        assert "Preferred" in str(caught.value)
        assert "Ignored" not in str(caught.value)

    def test_fastapi_detail_without_messages_uses_http_reason(self) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(422, {"detail": [{"input": "secret"}]}))
        assert "Unprocessable Entity" in str(caught.value)
        assert "secret" not in str(caught.value)

    @pytest.mark.parametrize("status_code", [200, 500])
    def test_result_string_error_message(self, status_code: int) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(
                self._make_response(status_code, {"ok": 0, "result": "Unknown incident"})
            )
        assert "Unknown incident" in str(caught.value)

    def test_200_with_error_status_raises_api_error(self) -> None:
        """Some endpoints return HTTP 200 with {"status": "error", ...} bodies."""
        resp = self._make_response(
            200, {"status": "error", "message": "Missing required grouporder parameter"}
        )
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert "Missing required grouporder parameter" in str(exc_info.value)
        assert exc_info.value.status_code == 200

    def test_200_with_not_found_error_raises_not_found(self) -> None:
        resp = self._make_response(200, {"status": "error", "message": "resource not found"})
        with pytest.raises(NotFoundError):
            raise_for_status(resp)

    def test_200_with_error_status_uses_body_status_code(self) -> None:
        resp = self._make_response(
            200, {"status": "error", "message": "bad input", "status_code": 400}
        )
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.status_code == 400

    def test_200_with_success_status_does_not_raise(self) -> None:
        resp = self._make_response(200, {"status": "Success", "data": {"tags": []}})
        raise_for_status(resp)  # Should not raise

    def test_200_with_failed_datasearch_execution_raises(self) -> None:
        body = {
            "result": [],
            "status": {
                "execution": "FAILED",
                "count": 1,
                "message": "Invalid query field",
                "status_code": 400,
            },
        }
        response = self._make_response(200, body, {"x-request-id": "query-failed"})
        with pytest.raises(APIError) as caught:
            raise_for_status(response)
        assert caught.value.status_code == 400
        assert caught.value.body == body
        assert caught.value.request_id == "query-failed"
        assert caught.value.request_method == "GET"
        assert caught.value.request_path == "/api/v2/test"
        assert "Invalid query field" in str(caught.value)

    @pytest.mark.parametrize("status_code", [None, False, "400"])
    def test_failed_execution_does_not_guess_status_code(self, status_code: object) -> None:
        response = self._make_response(
            200, {"status": {"execution": "FAILED", "status_code": status_code}}
        )
        with pytest.raises(APIError) as caught:
            raise_for_status(response)
        assert caught.value.status_code == 200

    def test_failed_execution_without_a_message_names_the_query_and_endpoint(self) -> None:
        body = {"result": [], "status": {"count": 25, "execution": "FAILED", "status_code": 200}}
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(200, body))
        rendered = str(caught.value)
        assert "Unknown error" not in rendered
        assert "execution=FAILED" in rendered
        assert "GET /api/v2/test" in rendered
        assert caught.value.status_code == 200

    def test_failed_execution_keeps_the_api_message_alongside_the_diagnosis(self) -> None:
        body = {"status": {"execution": "FAILED", "message": "query timed out"}}
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(200, body))
        rendered = str(caught.value)
        assert "execution=FAILED" in rendered
        assert "query timed out" in rendered

    def test_failed_execution_reporting_a_missing_resource_stays_a_not_found(self) -> None:
        body = {"status": {"execution": "FAILED", "message": "incident not found"}}
        with pytest.raises(NotFoundError) as caught:
            raise_for_status(self._make_response(200, body))
        assert "execution=FAILED" in str(caught.value)

    def test_a_200_error_envelope_that_is_not_a_datasearch_keeps_its_own_message(self) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(200, {"ok": 0, "message": "quota exceeded"}))
        rendered = str(caught.value)
        assert "quota exceeded" in rendered
        assert "execution=FAILED" not in rendered

    def test_successful_datasearch_execution_does_not_raise(self) -> None:
        response = self._make_response(
            200, {"result": [], "status": {"execution": "SUCCESS", "count": 0}}
        )
        raise_for_status(response)

    def test_200_with_non_dict_body_does_not_raise(self) -> None:
        resp = httpx.Response(
            200,
            json=[{"status": "error"}],
            request=httpx.Request("GET", "https://test.goskope.com/api/v2/test"),
        )
        raise_for_status(resp)  # Should not raise

    @pytest.mark.parametrize(
        "body",
        [
            {"ok": 0, "message": "Invalid datasearch query"},
            {"ok": False, "error": "Invalid query"},
            {"success": False, "message": "AICC query failed"},
        ],
    )
    def test_200_with_explicit_failure_envelope(self, body: dict) -> None:
        with pytest.raises(APIError) as exc_info:
            raise_for_status(self._make_response(200, body))
        assert exc_info.value.status_code == 200
        assert exc_info.value.body == body

    @pytest.mark.parametrize(
        "body",
        [
            {"ok": 1, "data": []},
            {"ok": None, "data": []},
            {"ok": "", "data": []},
            {"success": True, "data": []},
            {"success": None, "data": []},
            {"data": [{"success": False}]},
        ],
    )
    def test_other_json_objects_are_not_failure_envelopes(self, body: dict) -> None:
        raise_for_status(self._make_response(200, body))

    @pytest.mark.parametrize("status", [200, 401, 403, 404, 429, 500])
    def test_error_request_context_excludes_query_string(self, status: int) -> None:
        response = httpx.Response(
            status,
            json={"status": "error", "message": "Operation failed"},
            headers={"x-request-id": "request-456"},
            request=httpx.Request(
                "POST", "https://test.goskope.com/api/v2/test?private_query=value"
            ),
        )
        with pytest.raises(APIError) as exc_info:
            raise_for_status(response)
        assert exc_info.value.request_method == "POST"
        assert exc_info.value.request_path == "/api/v2/test"
        assert exc_info.value.request_id == "request-456"

    def test_error_without_attached_request(self) -> None:
        with pytest.raises(APIError) as exc_info:
            raise_for_status(httpx.Response(400, json={"message": "Invalid"}))
        assert exc_info.value.request_method is None
        assert exc_info.value.request_path is None

    @pytest.mark.parametrize("status", [200, 204])
    def test_successful_non_json_response(self, status: int) -> None:
        raise_for_status(httpx.Response(status, content=b"file contents" if status == 200 else b""))

    def test_400_error_path_unchanged_by_error_body_handling(self) -> None:
        """Non-2xx handling is unaffected by the 200-with-error-body logic."""
        resp = self._make_response(400, {"status": "error", "message": "bad request"})
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.status_code == 400
        assert "bad request" in str(exc_info.value)

    def test_list_message_is_joined(self) -> None:
        """The Netskope API returns ``message`` as a list for some validation errors."""
        resp = self._make_response(
            400,
            {
                "message": [
                    "property urls should not exist",
                    "data should not be null or undefined",
                ],
                "error": "Bad Request",
                "statusCode": 400,
            },
        )
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        rendered = str(exc_info.value)
        assert "property urls should not exist" in rendered
        assert "data should not be null or undefined" in rendered

    @pytest.mark.parametrize(
        "body",
        [
            {"execution": "FAILED", "message": "Invalid query field", "status_code": 400},
            {
                "result": [],
                "execution": "FAILED",
                "status": {"count": 0},
                "message": "Invalid query field",
                "status_code": 400,
            },
        ],
    )
    def test_200_with_top_level_failed_execution_raises(self, body: dict) -> None:
        with pytest.raises(APIError) as caught:
            raise_for_status(self._make_response(200, body))
        assert caught.value.status_code == 400
        assert "Invalid query field" in str(caught.value)

    @pytest.mark.parametrize("execution", ["COMPLETE", "SUCCESS", "failed", 0])
    def test_200_with_other_top_level_execution_does_not_raise(self, execution: object) -> None:
        raise_for_status(
            self._make_response(200, {"result": [], "execution": execution, "status": {"count": 0}})
        )

    def test_retry_after_http_date_is_seconds_until_the_deadline(self) -> None:
        deadline = datetime.now(UTC) + timedelta(seconds=45)
        resp = self._make_response(
            429,
            {"message": "Rate limited"},
            headers={"retry-after": format_datetime(deadline, usegmt=True)},
        )
        with pytest.raises(RateLimitError) as caught:
            raise_for_status(resp)
        assert caught.value.retry_after is not None
        assert 40.0 <= caught.value.retry_after <= 45.0

    def test_retry_after_in_the_past_is_zero(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=30)
        resp = self._make_response(
            429,
            {"message": "Rate limited"},
            headers={"retry-after": format_datetime(past, usegmt=True)},
        )
        with pytest.raises(RateLimitError) as caught:
            raise_for_status(resp)
        assert caught.value.retry_after == 0.0

    @pytest.mark.parametrize("raw", ["not-a-date", "", "   "])
    def test_unparsable_retry_after_is_unknown(self, raw: str) -> None:
        resp = self._make_response(429, {"message": "Rate limited"}, headers={"retry-after": raw})
        with pytest.raises(RateLimitError) as caught:
            raise_for_status(resp)
        assert caught.value.retry_after is None

    def test_retry_after_keeps_the_five_minute_cap(self) -> None:
        resp = self._make_response(429, {"message": "Slow"}, headers={"retry-after": "9000"})
        with pytest.raises(RateLimitError) as caught:
            raise_for_status(resp)
        assert caught.value.retry_after == 300.0


class TestParseRetryAfter:
    """The shared Retry-After reader used by the retry policy and RateLimitError."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(None, None), ("", None), ("30", 30.0), ("0", 0.0), ("-5", 0.0), ("2.5", 2.5)],
    )
    def test_delay_seconds(self, raw: str | None, expected: float | None) -> None:
        assert parse_retry_after(raw) == expected

    @pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "Infinity"])
    def test_non_finite_delays_are_unknown(self, raw: str) -> None:
        """A NaN or infinite delay is no delay at all; sleeping on it never ends."""
        assert parse_retry_after(raw) is None

    def test_non_finite_delay_does_not_reach_the_rate_limit_error(self) -> None:
        response = httpx.Response(
            429,
            json={"message": "Rate limited"},
            headers={"retry-after": "nan"},
            request=httpx.Request("GET", "https://t.goskope.com/api/v2/events"),
        )
        with pytest.raises(RateLimitError) as caught:
            raise_for_status(response)
        assert caught.value.retry_after is None

    def test_http_date_is_uncapped_here(self) -> None:
        deadline = datetime.now(UTC) + timedelta(seconds=600)
        parsed = parse_retry_after(format_datetime(deadline, usegmt=True))
        assert parsed is not None
        assert 595.0 <= parsed <= 600.0
