"""Tests for the NPA policy namespace with mocked HTTP.

``client.npa`` is not wired onto the clients yet, so resources are
instantiated directly against the client transports.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.npa_policy import NpaPolicyGroup, NpaPolicyRule
from netskope.resources.npa import AsyncNpaResource, NpaResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_RULES_URL = f"{_BASE}/api/v2/policy/npa/rules"
_GROUPS_URL = f"{_BASE}/api/v2/policy/npa/policygroups"
_NAME_VALIDATION_URL = f"{_BASE}/api/v2/infrastructure/npa/namevalidation"
_SEARCH_URL = f"{_BASE}/api/v2/infrastructure/npa/search"

_RULE = {
    "rule_id": 42,
    "rule_name": "Allow SSH",
    "enabled": "1",
    "group_id": "7",
    "group_name": "Engineering",
    "action": "allow",
    "rule_data": {"match_criteria_action": {"action_name": "allow"}},
}

_GROUP = {"group_id": 7, "group_name": "Engineering"}

# Minimal API-valid rule_data (the API rejects rule creation without one).
_RULE_DATA = {
    "policy_type": "private-app",
    "match_criteria_action": {"action_name": "allow"},
    "privateApps": ["ssh-server"],
}


def _npa(client: NetskopeClient) -> NpaResource:
    return NpaResource(client._transport)


def _anpa(aclient: AsyncNetskopeClient) -> AsyncNpaResource:
    return AsyncNpaResource(aclient._transport)


class TestNpaPolicyRulesResource:
    """Tests for the sync NPA policy rules resource."""

    @respx.mock
    def test_list_url_params_and_extraction(self, client: NetskopeClient) -> None:
        """list() hits GET /rules with filter/fields/sortby/sortorder + limit/offset."""
        route = respx.get(_RULES_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"rules": [_RULE]}, "status": {"total": 1}}
            )
        )
        rules = list(
            _npa(client).policy.rules.list(
                filter_expr="rule_name eq 'Allow SSH'",
                fields=["rule_id", "rule_name"],
                sort_by="rule_name",
                sort_order="asc",
                page_size=25,
            )
        )
        assert len(rules) == 1
        assert isinstance(rules[0], NpaPolicyRule)
        assert rules[0].rule_id == 42
        assert rules[0].rule_name == "Allow SSH"
        params = route.calls.last.request.url.params
        assert params["filter"] == "rule_name eq 'Allow SSH'"
        assert params["fields"] == "rule_id,rule_name"
        assert params["sortby"] == "rule_name"
        assert params["sortorder"] == "asc"
        assert params["limit"] == "25"
        assert params["offset"] == "0"

    @respx.mock
    @pytest.mark.parametrize(
        "body",
        [
            {"data": [_RULE]},
            {"data": {"rules": [_RULE]}},
            {"rules": [_RULE]},
            [_RULE],
        ],
    )
    def test_list_envelope_variations(self, client: NetskopeClient, body: object) -> None:
        empty = httpx.Response(200, json={"data": []})
        respx.get(_RULES_URL).mock(side_effect=[httpx.Response(200, json=body), empty, empty])
        rules = list(_npa(client).policy.rules.list())
        assert len(rules) == 1
        assert rules[0].rule_id == 42

    @respx.mock
    def test_list_paginates_with_offset(self, client: NetskopeClient) -> None:
        """The paginator advances offset by page_size until an empty page."""
        page1 = [{**_RULE, "rule_id": i} for i in range(2)]
        route = respx.get(_RULES_URL).mock(
            side_effect=[
                httpx.Response(200, json={"data": page1}),
                httpx.Response(200, json={"data": []}),
                httpx.Response(200, json={"data": []}),
            ]
        )
        rules = list(_npa(client).policy.rules.list(page_size=2))
        assert [r.rule_id for r in rules] == [0, 1]
        offsets = [call.request.url.params["offset"] for call in route.calls]
        assert offsets == ["0", "2", "4"]

    @respx.mock
    def test_get_url_and_fields(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        rule = _npa(client).policy.rules.get(42, fields=["rule_id", "rule_name"])
        assert route.calls.last.request.method == "GET"
        assert route.calls.last.request.url.params["fields"] == "rule_id,rule_name"
        assert rule.rule_name == "Allow SSH"
        assert rule.group_name == "Engineering"

    @respx.mock
    def test_create_payload_enabled_string(self, client: NetskopeClient) -> None:
        """create() sends enabled as the string "1"/"0", never a boolean."""
        route = respx.post(_RULES_URL).mock(return_value=httpx.Response(200, json={"data": _RULE}))
        rule = _npa(client).policy.rules.create(
            rule_name="Allow SSH", group_id="7", rule_data=_RULE_DATA
        )
        assert sent_json(route) == {
            "rule_name": "Allow SSH",
            "group_id": "7",
            "enabled": "1",
            "rule_data": _RULE_DATA,
        }
        assert isinstance(rule, NpaPolicyRule)
        assert rule.rule_id == 42

    @respx.mock
    def test_create_disabled_with_rule_data_and_extra_fields(self, client: NetskopeClient) -> None:
        route = respx.post(_RULES_URL).mock(return_value=httpx.Response(200, json={"data": _RULE}))
        _npa(client).policy.rules.create(
            rule_name="Allow SSH",
            enabled=False,
            rule_data=_RULE_DATA,
            extra_fields={"description": "unit test"},
        )
        assert sent_json(route) == {
            "rule_name": "Allow SSH",
            "enabled": "0",
            "rule_data": _RULE_DATA,
            "description": "unit test",
        }

    @respx.mock
    def test_create_requires_name_or_body_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _npa(client).policy.rules.create()
        assert len(respx.calls) == 0

    @respx.mock
    def test_create_requires_rule_data_no_http(self, client: NetskopeClient) -> None:
        """The API rejects rule creation without rule_data — guard client-side."""
        with pytest.raises(ValidationError, match="rule_data"):
            _npa(client).policy.rules.create(rule_name="Allow SSH", group_id="7")
        with pytest.raises(ValidationError, match="rule_data"):
            _npa(client).policy.rules.create(rule_name="Allow SSH", rule_data={})
        assert len(respx.calls) == 0

    @respx.mock
    def test_create_rule_data_via_extra_fields(self, client: NetskopeClient) -> None:
        """extra_fields may supply rule_data instead of the dedicated argument."""
        route = respx.post(_RULES_URL).mock(return_value=httpx.Response(200, json={"data": _RULE}))
        _npa(client).policy.rules.create(
            rule_name="Allow SSH",
            extra_fields={"rule_data": _RULE_DATA},
        )
        assert sent_json(route) == {
            "rule_name": "Allow SSH",
            "enabled": "1",
            "rule_data": _RULE_DATA,
        }

    @respx.mock
    def test_update_only_set_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        _npa(client).policy.rules.update(42, enabled=False)
        assert sent_json(route) == {"enabled": "0"}
        _npa(client).policy.rules.update(42, rule_name="Renamed", enabled=True)
        assert sent_json(route) == {"rule_name": "Renamed", "enabled": "1"}

    @respx.mock
    def test_update_empty_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _npa(client).policy.rules.update(42)
        assert len(respx.calls) == 0

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert _npa(client).policy.rules.delete(42) is None
        assert route.call_count == 1


class TestNpaPolicyGroupsResource:
    """Tests for the sync NPA policy groups resource."""

    @respx.mock
    def test_list_extraction_and_paginator_params(self, client: NetskopeClient) -> None:
        route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"policygroups": [_GROUP]}, "status": {"total": 1}}
            )
        )
        groups = _npa(client).policy.groups.list(page_size=10).to_list(max_items=10)
        assert len(groups) == 1
        assert isinstance(groups[0], NpaPolicyGroup)
        assert groups[0].group_id == 7
        assert groups[0].group_name == "Engineering"
        params = route.calls.last.request.url.params
        assert params["limit"] == "10"
        assert params["offset"] == "0"

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        group = _npa(client).policy.groups.get(7)
        assert route.calls.last.request.method == "GET"
        assert group.group_name == "Engineering"

    @respx.mock
    def test_create_with_explicit_anchor(self, client: NetskopeClient) -> None:
        """With anchor_group_id given, no list fetch happens and group_order is sent."""
        route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"group_id": "18", "group_name": "Engineering"}}
            )
        )
        group = _npa(client).policy.groups.create("Engineering", anchor_group_id=16)
        assert sent_json(route) == {
            "group_name": "Engineering",
            "group_order": {"group_id": "16", "order": "after"},
        }
        assert group.group_id == "18"
        assert len(respx.calls) == 1  # no GET for the anchor

    @respx.mock
    def test_create_auto_anchor_prefers_last_editable_group(self, client: NetskopeClient) -> None:
        """Without an anchor, create() lists groups and anchors after the last editable one."""
        respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"group_id": 1, "group_name": "Default", "can_be_edited_deleted": "False"},
                        {"group_id": 16, "group_name": "Custom", "can_be_edited_deleted": "True"},
                        {"group_id": 17, "group_name": "Pinned", "can_be_edited_deleted": "False"},
                    ]
                },
            )
        )
        post_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"group_id": "18", "group_name": "x"}})
        )
        _npa(client).policy.groups.create("x", order="before")
        assert sent_json(post_route) == {
            "group_name": "x",
            "group_order": {"group_id": "16", "order": "before"},
        }

    @respx.mock
    def test_create_auto_anchor_falls_back_to_last_group(self, client: NetskopeClient) -> None:
        respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"group_id": 1, "group_name": "A", "can_be_edited_deleted": "False"},
                        {"group_id": 2, "group_name": "B", "can_be_edited_deleted": "False"},
                    ]
                },
            )
        )
        post_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        _npa(client).policy.groups.create("Engineering")
        assert sent_json(post_route) == {
            "group_name": "Engineering",
            "group_order": {"group_id": "2", "order": "after"},
        }

    @respx.mock
    def test_create_no_groups_omits_group_order(self, client: NetskopeClient) -> None:
        respx.get(_GROUPS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        post_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        _npa(client).policy.groups.create("Engineering")
        assert sent_json(post_route) == {"group_name": "Engineering"}

    @respx.mock
    def test_create_invalid_order_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError, match="order"):
            _npa(client).policy.groups.create("Engineering", order="above")
        assert len(respx.calls) == 0

    @respx.mock
    def test_update_payload(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        _npa(client).policy.groups.update(7, group_name="Renamed")
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"group_name": "Renamed"}

    @respx.mock
    def test_delete(self, client: NetskopeClient) -> None:
        route = respx.delete(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        assert _npa(client).policy.groups.delete(7) is None
        assert route.call_count == 1


class TestNpaContainer:
    """Tests for the sync NPA container utilities."""

    @respx.mock
    def test_validate_name_params(self, client: NetskopeClient) -> None:
        route = respx.get(_NAME_VALIDATION_URL).mock(
            return_value=httpx.Response(200, json={"status": "success", "data": {"valid": True}})
        )
        body = _npa(client).validate_name("private_app", "SSH Server")
        params = route.calls.last.request.url.params
        assert params["resourceType"] == "private_app"
        assert params["name"] == "SSH Server"
        assert body["data"]["valid"] is True

    @respx.mock
    def test_validate_name_invalid_type_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            _npa(client).validate_name("bogus", "x")
        assert len(respx.calls) == 0

    @respx.mock
    def test_search_url_and_query(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_SEARCH_URL}/publishers").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        _npa(client).search("publishers", "prod")
        assert route.calls.last.request.url.params["query"] == "prod"

    @respx.mock
    def test_search_invalid_type_no_http(self, client: NetskopeClient) -> None:
        """Only publishers/private_apps are searchable; anything else fails client-side."""
        with pytest.raises(ValidationError):
            _npa(client).search("policies", "x")
        with pytest.raises(ValidationError):
            _npa(client).search("../admin", "x")
        assert len(respx.calls) == 0


class TestAsyncNpaPolicy:
    """Tests for the async NPA namespace."""

    @respx.mock
    async def test_rules_list_url_and_extraction(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_RULES_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"rules": [_RULE]}, "status": {"total": 1}}
            )
        )
        rules = await _anpa(aclient).policy.rules.list(sort_by="rule_name").to_list()
        assert len(rules) == 1
        assert rules[0].rule_id == 42
        params = route.calls.last.request.url.params
        assert params["sortby"] == "rule_name"
        assert params["limit"] == "100"
        assert params["offset"] == "0"

    @respx.mock
    async def test_rule_get(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        rule = await _anpa(aclient).policy.rules.get(42)
        assert route.call_count == 1
        assert rule.rule_name == "Allow SSH"

    @respx.mock
    async def test_rule_create_payload(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_RULES_URL).mock(return_value=httpx.Response(200, json={"data": _RULE}))
        await _anpa(aclient).policy.rules.create(
            rule_name="Allow SSH", group_id="7", enabled=False, rule_data=_RULE_DATA
        )
        assert sent_json(route) == {
            "rule_name": "Allow SSH",
            "group_id": "7",
            "enabled": "0",
            "rule_data": _RULE_DATA,
        }

    @respx.mock
    async def test_rule_create_requires_rule_data_no_http(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with pytest.raises(ValidationError, match="rule_data"):
            await _anpa(aclient).policy.rules.create(rule_name="Allow SSH", group_id="7")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_rule_update_and_delete(self, aclient: AsyncNetskopeClient) -> None:
        patch_route = respx.patch(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        delete_route = respx.delete(f"{_RULES_URL}/42").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await _anpa(aclient).policy.rules.update(42, rule_name="Renamed", enabled=True)
        assert sent_json(patch_route) == {"rule_name": "Renamed", "enabled": "1"}
        assert await _anpa(aclient).policy.rules.delete(42) is None
        assert delete_route.call_count == 1

    @respx.mock
    async def test_rule_update_empty_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _anpa(aclient).policy.rules.update(42)
        assert len(respx.calls) == 0

    @respx.mock
    async def test_groups_roundtrip(self, aclient: AsyncNetskopeClient) -> None:
        list_route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200, json={"data": {"policygroups": [_GROUP]}, "status": {"total": 1}}
            )
        )
        create_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        patch_route = respx.patch(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        delete_route = respx.delete(f"{_GROUPS_URL}/7").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        npa = _anpa(aclient)
        groups = await npa.policy.groups.list().to_list()
        assert groups[0].group_name == "Engineering"
        group = await npa.policy.groups.create("Engineering", anchor_group_id="16")
        assert sent_json(create_route) == {
            "group_name": "Engineering",
            "group_order": {"group_id": "16", "order": "after"},
        }
        assert group.group_id == 7
        await npa.policy.groups.update(7, group_name="Renamed")
        assert sent_json(patch_route) == {"group_name": "Renamed"}
        assert await npa.policy.groups.delete(7) is None
        assert list_route.call_count == 1
        assert delete_route.call_count == 1

    @respx.mock
    async def test_group_create_auto_anchor(self, aclient: AsyncNetskopeClient) -> None:
        """Without an anchor, the async create also lists groups first."""
        list_route = respx.get(_GROUPS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "policygroups": [
                            {"group_id": 7, "group_name": "E", "can_be_edited_deleted": "True"}
                        ]
                    }
                },
            )
        )
        create_route = respx.post(_GROUPS_URL).mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        await _anpa(aclient).policy.groups.create("Engineering")
        assert list_route.call_count == 1
        assert sent_json(create_route) == {
            "group_name": "Engineering",
            "group_order": {"group_id": "7", "order": "after"},
        }

    @respx.mock
    async def test_group_create_invalid_order_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError, match="order"):
            await _anpa(aclient).policy.groups.create("Engineering", order="under")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_validate_name_and_search(self, aclient: AsyncNetskopeClient) -> None:
        validate_route = respx.get(_NAME_VALIDATION_URL).mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        search_route = respx.get(f"{_SEARCH_URL}/private_apps").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        npa = _anpa(aclient)
        await npa.validate_name("publisher", "My Publisher")
        params = validate_route.calls.last.request.url.params
        assert params["resourceType"] == "publisher"
        assert params["name"] == "My Publisher"
        await npa.search("private_apps", "ssh")
        assert search_route.calls.last.request.url.params["query"] == "ssh"

    @respx.mock
    async def test_validate_name_invalid_type_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await _anpa(aclient).validate_name("publishers", "x")  # plural is a search type
        with pytest.raises(ValidationError):
            await _anpa(aclient).search("publisher", "x")  # singular is a validation type
        assert len(respx.calls) == 0
