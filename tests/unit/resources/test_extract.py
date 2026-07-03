"""Tests for the shared envelope-extraction and ID-safety helpers."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources._extract import extract_item, extract_list, quote_id, validate_id
from tests.unit.resources.conftest import sent_json


class TestExtractList:
    """Envelope shapes handled by extract_list."""

    def test_bare_list(self) -> None:
        assert extract_list([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]

    def test_bare_list_drops_non_dicts(self) -> None:
        assert extract_list([{"a": 1}, "junk", 3]) == [{"a": 1}]

    def test_result_key(self) -> None:
        assert extract_list({"result": [{"a": 1}]}) == [{"a": 1}]

    def test_data_list(self) -> None:
        assert extract_list({"data": [{"a": 1}]}) == [{"a": 1}]

    def test_data_nested_key(self) -> None:
        body = {"data": {"urllists": [{"id": 1}]}}
        assert extract_list(body, "urllists") == [{"id": 1}]

    def test_data_nested_key_tries_each_key(self) -> None:
        body = {"data": {"publishers": [{"id": 2}]}}
        assert extract_list(body, "urllists", "publishers") == [{"id": 2}]

    def test_top_level_nested_key(self) -> None:
        assert extract_list({"tunnels": [{"id": 3}]}, "tunnels") == [{"id": 3}]

    def test_resources_key(self) -> None:
        assert extract_list({"Resources": [{"id": "u1"}]}) == [{"id": "u1"}]

    def test_result_takes_precedence_over_data(self) -> None:
        body = {"result": [{"a": 1}], "data": [{"b": 2}]}
        assert extract_list(body) == [{"a": 1}]

    def test_unknown_envelope_returns_empty(self) -> None:
        assert extract_list({"something": "else"}) == []
        assert extract_list({"data": "not-a-list"}) == []


class TestExtractItem:
    """Single-item extraction from response envelopes."""

    def test_data_dict(self) -> None:
        assert extract_item({"data": {"id": 1}}) == {"id": 1}

    def test_data_single_item_list(self) -> None:
        assert extract_item({"data": [{"id": 1}]}) == {"id": 1}

    def test_data_multi_item_list_returns_body(self) -> None:
        body = {"data": [{"id": 1}, {"id": 2}]}
        assert extract_item(body) == body

    def test_no_data_returns_body(self) -> None:
        assert extract_item({"id": 5}) == {"id": 5}

    def test_nested_key_inside_data(self) -> None:
        body = {"data": {"publisher": {"id": 9}}}
        assert extract_item(body, "publisher") == {"id": 9}


class TestValidateId:
    """Path-segment ID validation."""

    def test_valid_string_passes(self) -> None:
        assert validate_id("abc-123_XYZ") == "abc-123_XYZ"

    def test_int_passes_through_as_str(self) -> None:
        assert validate_id(42) == "42"

    @pytest.mark.parametrize("bad", ["a/b", "a b", "", "a?x=1", "../etc", "a\nb"])
    def test_invalid_strings_raise(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            validate_id(bad)

    def test_error_message_uses_name(self) -> None:
        with pytest.raises(ValidationError, match="list_id"):
            validate_id("bad/id", name="list_id")


class TestQuoteId:
    """Percent-encoding of freer-form identifiers."""

    def test_plain_value_unchanged(self) -> None:
        assert quote_id("abc-123") == "abc-123"

    def test_slash_is_encoded(self) -> None:
        assert quote_id("a/b") == "a%2Fb"

    def test_email_like_value(self) -> None:
        assert quote_id("alice@example.com") == "alice%40example.com"

    @pytest.mark.parametrize("bad", ["", "a b", ".", "..", "a\x00b"])
    def test_unsafe_values_raise(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            quote_id(bad)


class TestDeleteWithBody:
    """_delete on the base resources supports an optional JSON body."""

    @respx.mock
    def test_sync_delete_sends_json_body(self, client: NetskopeClient) -> None:
        route = respx.delete("https://t.goskope.com/api/v2/whatever").mock(
            return_value=httpx.Response(200, json={})
        )
        client.url_lists._delete("/api/v2/whatever", json={"ids": [1, 2]})
        assert sent_json(route) == {"ids": [1, 2]}

    @respx.mock
    def test_sync_delete_without_json_has_no_body(self, client: NetskopeClient) -> None:
        route = respx.delete("https://t.goskope.com/api/v2/whatever").mock(
            return_value=httpx.Response(200, json={})
        )
        client.url_lists._delete("/api/v2/whatever")
        assert route.calls.last.request.read() == b""

    @respx.mock
    async def test_async_delete_sends_json_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.delete("https://t.goskope.com/api/v2/whatever").mock(
            return_value=httpx.Response(200, json={})
        )
        await aclient.url_lists._delete("/api/v2/whatever", json={"ids": [1]})
        assert sent_json(route) == {"ids": [1]}
