"""Tests for the shared envelope-extraction and ID-safety helpers."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.core.ids import (
    extract_item,
    extract_list,
    id_strings,
    quote_id,
    validate_id,
)
from netskope.exceptions import ValidationError
from tests.unit.resources.conftest import CONTRACT_BASE, sent_json


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

    def test_trailing_newline_never_reaches_a_publisher_path(self) -> None:
        """npa_publishers.yaml:1407-1415 declares an integer path ID."""
        with (
            respx.mock(assert_all_mocked=True) as mock,
            NetskopeClient(
                tenant="example.goskope.coken",
                allow_custom_tenant=True,
                api_token="synthetic-token",
            ) as sdk,
        ):
            with pytest.raises(ValidationError):
                sdk.publishers.get("1\n")
            assert not mock.calls

    def test_zero_is_a_usable_id(self) -> None:
        assert validate_id(0) == "0"

    @pytest.mark.parametrize("bad", [-1, -3, -12345])
    def test_negative_ints_raise(self, bad: int) -> None:
        with pytest.raises(ValidationError, match="Invalid id format"):
            validate_id(bad)

    @pytest.mark.parametrize("bad", [True, False])
    def test_bools_raise_despite_being_ints(self, bad: bool) -> None:
        with pytest.raises(ValidationError):
            validate_id(bad)

    def test_a_negative_id_never_reaches_the_wire(self, client: NetskopeClient) -> None:
        with respx.mock:
            catch_all = respx.route().mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError):
                client.url_lists.get(-3)
            assert catch_all.call_count == 0

    def test_id_strings_rejects_a_negative_member(self) -> None:
        with pytest.raises(ValidationError, match="app_ids"):
            id_strings([1, -5], "app_ids")


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


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_PUBLISHERS_URL = f"{CONTRACT_BASE}/api/v2/infrastructure/publishers"
_LBROKERS_URL = f"{CONTRACT_BASE}/api/v2/infrastructure/lbrokers"
_PROFILES_URL = f"{CONTRACT_BASE}/api/v2/infrastructure/publisherupgradeprofiles"
_APPS_URL = f"{CONTRACT_BASE}/api/v2/steering/apps/private"
_TUNNELS_URL = f"{CONTRACT_BASE}/api/v2/steering/ipsec/tunnels"
_TRAVERSING_IDS = ("../tags", "7/../../publishers", "3/../pops", "..")


def _sync_id_calls(client: NetskopeClient, app_id: Any) -> list[Any]:
    return [
        lambda: client.private_apps.get(app_id),
        lambda: client.private_apps.update(app_id, extra_fields={"host": "h"}),
        lambda: client.private_apps.replace(app_id, {"host": "h"}),
        lambda: client.private_apps.delete(app_id),
        lambda: client.steering.get_tunnel(app_id),
        lambda: client.steering.update_tunnel(app_id, site="dc"),
        lambda: client.steering.delete_tunnel(app_id),
        lambda: client.npa.local_brokers.get(app_id),
        lambda: client.npa.local_brokers.update(app_id, city="Cupertino"),
        lambda: client.npa.local_brokers.delete(app_id),
        lambda: client.npa.local_brokers.create_registration_token(app_id),
        lambda: client.npa.upgrade_profiles.get(app_id),
        lambda: client.npa.upgrade_profiles.delete(app_id),
        lambda: client.publishers.delete(app_id),
    ]


def _async_id_calls(client: AsyncNetskopeClient, app_id: Any) -> list[Any]:
    return [
        lambda: client.private_apps.get(app_id),
        lambda: client.private_apps.update(app_id, extra_fields={"host": "h"}),
        lambda: client.private_apps.replace(app_id, {"host": "h"}),
        lambda: client.private_apps.delete(app_id),
        lambda: client.steering.get_tunnel(app_id),
        lambda: client.steering.update_tunnel(app_id, site="dc"),
        lambda: client.steering.delete_tunnel(app_id),
        lambda: client.npa.local_brokers.get(app_id),
        lambda: client.npa.local_brokers.update(app_id, city="Cupertino"),
        lambda: client.npa.local_brokers.delete(app_id),
        lambda: client.npa.local_brokers.create_registration_token(app_id),
        lambda: client.npa.upgrade_profiles.get(app_id),
        lambda: client.npa.upgrade_profiles.delete(app_id),
        lambda: client.publishers.delete(app_id),
    ]


@pytest.mark.parametrize("bad_id", _TRAVERSING_IDS)
@respx.mock
def test_legacy_path_ids_are_validated_before_any_request(
    contract_client: NetskopeClient, bad_id: str
) -> None:
    """A crafted id is refused instead of retargeting the request (see citations above)."""
    for call in _sync_id_calls(contract_client, bad_id):
        with pytest.raises(ValidationError, match="Invalid"):
            call()
    assert len(respx.calls) == 0


@pytest.mark.parametrize("bad_id", _TRAVERSING_IDS)
@respx.mock
async def test_async_legacy_path_ids_are_validated_before_any_request(
    contract_aclient: AsyncNetskopeClient, bad_id: str
) -> None:
    """The async mirrors validate the same ids at the same sites."""
    for call in _async_id_calls(contract_aclient, bad_id):
        with pytest.raises(ValidationError, match="Invalid"):
            await call()
    assert len(respx.calls) == 0


@respx.mock
def test_well_formed_integer_ids_still_reach_their_declared_path(
    contract_client: NetskopeClient,
) -> None:
    """Validation is not a behaviour change for the ids the contract declares."""
    app = respx.get(f"{_APPS_URL}/7").mock(
        return_value=httpx.Response(200, json={"data": {"app_id": 7}})
    )
    tunnel = respx.delete(f"{_TUNNELS_URL}/3").mock(return_value=httpx.Response(204))
    broker = respx.get(f"{_LBROKERS_URL}/11").mock(
        return_value=httpx.Response(200, json={"data": {"id": 11}})
    )
    profile = respx.delete(f"{_PROFILES_URL}/5").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    publisher = respx.delete(f"{_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )

    assert contract_client.private_apps.get(7).app_id == 7
    contract_client.steering.delete_tunnel(3)
    assert contract_client.npa.local_brokers.get(11).id == 11
    contract_client.npa.upgrade_profiles.delete(5)
    contract_client.publishers.delete(6)

    assert all(route.call_count == 1 for route in (app, tunnel, broker, profile, publisher))
