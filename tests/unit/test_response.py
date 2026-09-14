"""Behavior of original-response access and lazy typed parsing."""

from __future__ import annotations

import httpx
import pytest

from netskope.exceptions import NotFoundError, PaginationError, ResponseValidationError
from netskope.models.publishers import Publisher
from netskope.response import ApiResponse


def response(body: object) -> httpx.Response:
    return httpx.Response(
        200,
        json=body,
        headers={"x-request-id": "request-42"},
        request=httpx.Request("POST", "https://t.goskope.com/api/v2/infrastructure/publishers"),
    )


def test_parse_is_lazy_and_cached() -> None:
    calls = 0

    def parse(raw: httpx.Response) -> Publisher:
        nonlocal calls
        calls += 1
        return Publisher.model_validate(raw.json())

    result = ApiResponse(response({"publisher_id": 42, "future": {"enabled": True}}), parse)
    assert calls == 0
    assert result.json()["publisher_id"] == 42
    publisher = result.parse()
    assert publisher.publisher_id == 42
    assert result.parse() is publisher
    assert calls == 1


def test_none_result_is_cached() -> None:
    calls = 0

    def parse(raw: httpx.Response) -> None:
        nonlocal calls
        calls += 1

    result = ApiResponse(response({"status": "success"}), parse)
    assert result.parse() is None
    assert result.parse() is None
    assert calls == 1


def test_json_mutation_does_not_change_typed_result_or_original_content() -> None:
    result = ApiResponse(
        response({"publisher_id": 42, "future": {"enabled": True}}),
        lambda raw: Publisher.model_validate(raw.json()),
    )
    decoded = result.json()
    decoded["publisher_id"] = 999
    decoded["future"]["enabled"] = False
    assert result.parse().publisher_id == 42
    assert result.json()["future"] == {"enabled": True}


def test_validation_failure_preserves_original_without_exposing_values() -> None:
    body = {"publisher_id": {"token": "sensitive-response-value"}}
    result = ApiResponse(response(body), lambda raw: Publisher.model_validate(raw.json()))
    with pytest.raises(ResponseValidationError) as caught:
        result.parse()
    error = caught.value
    assert error.request_method == "POST"
    assert error.request_path == "/api/v2/infrastructure/publishers"
    assert error.request_id == "request-42"
    assert error.field_errors == ((("publisher_id",), "int_type"),)
    assert "sensitive-response-value" not in str(error)
    assert "sensitive-response-value" not in repr(error)
    assert "sensitive-response-value" not in repr(result)
    assert result.json() == body


@pytest.mark.parametrize(
    "content",
    [b"invalid-json", b'{"name": "caf\xc3(\xa9"}'],
    ids=["not-json", "undecodable-bytes"],
)
def test_invalid_json_remains_available_as_bytes(content: bytes) -> None:
    """A decode failure names the problem without quoting the body or a byte offset."""
    raw = httpx.Response(
        200,
        content=content,
        request=httpx.Request("GET", "https://t.goskope.com/api/v2/infrastructure/publishers"),
    )
    result = ApiResponse(raw, lambda item: Publisher.model_validate(item.json()))
    with pytest.raises(ResponseValidationError) as caught:
        result.parse()
    assert str(caught.value) == "The API response body is not valid JSON."
    assert caught.value.request_method == "GET"
    assert caught.value.request_path == "/api/v2/infrastructure/publishers"
    assert result.content == content
    assert result.status_code == 200


def test_headers_are_a_copy() -> None:
    result = ApiResponse(response({}), lambda raw: Publisher.model_validate(raw.json()))
    result.headers["x-request-id"] = "changed"
    assert result.request_id == "request-42"


def test_unattached_response_preserves_validation_error() -> None:
    result = ApiResponse(
        httpx.Response(200, json={"publisher_id": "invalid"}),
        lambda raw: Publisher.model_validate(raw.json()),
    )
    with pytest.raises(ResponseValidationError) as caught:
        result.parse()
    assert caught.value.request_method is None
    assert caught.value.request_path is None
    assert caught.value.field_errors == ((("publisher_id",), "int_parsing"),)


def test_decoder_diagnostic_reaches_the_caller() -> None:
    def parse(_: httpx.Response) -> Publisher:
        raise ValueError("Expected a publisher collection.")

    result = ApiResponse(response({"unexpected": True}), parse)
    with pytest.raises(ResponseValidationError) as caught:
        result.parse()
    assert "Expected a publisher collection." in str(caught.value)
    assert isinstance(caught.value.__cause__, ValueError)
    assert caught.value.request_path == "/api/v2/infrastructure/publishers"
    assert caught.value.request_id == "request-42"


def test_pagination_error_passes_through_with_request_context() -> None:
    def parse(_: httpx.Response) -> Publisher:
        raise PaginationError("The returned offset does not match the requested page.", offset=20)

    result = ApiResponse(response({"offset": 0}), parse)
    with pytest.raises(PaginationError) as caught:
        result.parse()
    assert caught.value.offset == 20
    assert caught.value.request_method == "POST"
    assert caught.value.request_path == "/api/v2/infrastructure/publishers"
    assert caught.value.request_id == "request-42"


def test_decoder_request_context_is_not_overwritten() -> None:
    def parse(_: httpx.Response) -> Publisher:
        raise NotFoundError(
            "Alert not found",
            status_code=404,
            request_method="GET",
            request_path="/api/v2/events/datasearch/alert",
            request_id="decoder-id",
        )

    result = ApiResponse(response({"result": []}), parse)
    with pytest.raises(NotFoundError) as caught:
        result.parse()
    assert caught.value.request_method == "GET"
    assert caught.value.request_path == "/api/v2/events/datasearch/alert"
    assert caught.value.request_id == "decoder-id"
