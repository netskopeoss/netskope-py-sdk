"""A declared record key owns its collection; competing collections are rejected."""

from __future__ import annotations

import pytest

from netskope.core.response_list import extract_response_list, parse_response_list
from netskope.models.devices import Device

AMBIGUOUS = "competing collections"


def test_declared_key_is_not_shadowed_by_an_empty_generic_list():
    body = {"result": [], "roles": [{"id": 1}], "count": 1}
    assert extract_response_list(body, "roles") == [{"id": 1}]


def test_declared_key_wins_over_a_populated_generic_list():
    body = {"data": [{"id": "generic"}], "roles": [{"id": "declared"}]}
    assert extract_response_list(body, "roles") == [{"id": "declared"}]


def test_declared_key_nested_in_the_data_envelope():
    body = {"success": True, "data": {"data": [{"id": 7}], "total_count": 1}}
    assert extract_response_list(body, "data") == [{"id": 7}]


@pytest.mark.parametrize(
    "body",
    [
        {"result": [], "data": [{"device_id": "d1"}], "total": 9},
        {"result": [], "data": []},
        {"result": [{"a": 1}], "Resources": [{"b": 2}]},
    ],
    ids=["empty-result-shadowing-data", "two-empty-lists", "result-and-resources"],
)
def test_competing_envelope_collections_are_rejected(body):
    with pytest.raises(ValueError, match=AMBIGUOUS):
        extract_response_list(body)


def test_two_declared_keys_in_one_envelope_are_rejected():
    body = {"users": [{"id": "u"}], "groups": [{"id": "g"}]}
    with pytest.raises(ValueError, match=AMBIGUOUS):
        extract_response_list(body, "users", "groups")


def test_a_declared_key_ends_the_search_for_generic_collections():
    body = {"result": [], "data": [], "devices": [{"device_id": "d1"}]}
    assert extract_response_list(body, "devices") == [{"device_id": "d1"}]


@pytest.mark.parametrize(
    "body,expected",
    [
        ([{"a": 1}], [{"a": 1}]),
        ({"result": [{"a": 1}]}, [{"a": 1}]),
        ({"data": [{"a": 1}]}, [{"a": 1}]),
        ({"Resources": [{"a": 1}]}, [{"a": 1}]),
        ({"data": {"users": [{"a": 1}]}}, [{"a": 1}]),
    ],
    ids=["plain-list", "result", "data", "resources", "nested-declared"],
)
def test_single_supported_envelope(body, expected):
    assert extract_response_list(body, "users") == expected


@pytest.mark.parametrize("body", [{}, {"result": {}}, {"result": [1]}, "text", None], ids=str)
def test_unsupported_bodies_are_rejected(body):
    with pytest.raises(ValueError, match="collection of objects"):
        extract_response_list(body, "users")


def test_parse_response_list_validates_the_declared_collection():
    body = {"result": [], "devices": [{"device_id": "d1", "hostname": "LAPTOP-1"}]}
    devices = parse_response_list(body, Device, "devices")
    assert [device.host_name for device in devices] == ["LAPTOP-1"]
