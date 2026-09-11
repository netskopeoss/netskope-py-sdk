"""R3S-C7: the NPA policy typed reads and group patch that no test executed.

``NpaPolicyRuleResponses.get``, ``NpaPolicyGroupResponses.get`` and
``NpaPolicyGroupResponses.update_request`` (plus their async mirrors) shipped
without running under ``tests/unit``.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.npa_policy import NpaPolicyGroup, NpaPolicyGroupPatch, NpaPolicyRule
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/policy/npa"
_RULES_URL = f"{_BASE}/rules"
_GROUPS_URL = f"{_BASE}/policygroups"

_RULE = {
    "rule_id": 18,
    "rule_name": "allow-ssh",
    "enabled": "1",
    "group_id": "3",
    "action": "allow",
    "rule_data": {"privateApps": ["ssh-box"]},
}
_GROUP = {"group_id": "3", "group_name": "engineering", "can_be_edited_deleted": "True"}


class TestNpaPolicyRuleResponses:
    """client.npa.policy.rules.with_response.get, sync and async."""

    @respx.mock
    def test_get_without_fields_sends_no_params(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/18").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        rule = client.npa.policy.rules.with_response.get(18).parse()
        assert not route.calls.last.request.url.params
        assert isinstance(rule, NpaPolicyRule)
        assert rule.rule_name == "allow-ssh"
        assert rule.enabled == "1"

    @respx.mock
    def test_get_joins_the_requested_fields(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/18").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        client.npa.policy.rules.with_response.get(18, fields=["rule_name", "enabled"])
        assert dict(route.calls.last.request.url.params) == {"fields": "rule_name,enabled"}

    def test_get_rejects_an_unusable_rule_id(self, client: NetskopeClient) -> None:
        with respx.mock:
            route = respx.route(host="t.goskope.com")
            with pytest.raises(ValidationError, match="rule_id"):
                client.npa.policy.rules.with_response.get("../3")
            assert not route.called

    @respx.mock
    async def test_async_get(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/18").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        response = await aclient.npa.policy.rules.with_response.get(18, fields=["rule_name"])
        assert dict(route.calls.last.request.url.params) == {"fields": "rule_name"}
        assert response.parse().rule_id == 18

    @respx.mock
    async def test_async_get_without_fields(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_RULES_URL}/18").mock(
            return_value=httpx.Response(200, json={"data": _RULE})
        )
        response = await aclient.npa.policy.rules.with_response.get(18)
        assert not route.calls.last.request.url.params
        assert response.parse().action == "allow"


class TestNpaPolicyGroupResponses:
    """client.npa.policy.groups.with_response.get / update_request."""

    @respx.mock
    def test_get(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_GROUPS_URL}/3").mock(
            return_value=httpx.Response(200, json={"data": _GROUP})
        )
        group = client.npa.policy.groups.with_response.get(3).parse()
        assert route.calls.last.request.method == "GET"
        assert isinstance(group, NpaPolicyGroup)
        assert group.group_name == "engineering"

    @respx.mock
    def test_update_request_patches_only_the_named_fields(self, client: NetskopeClient) -> None:
        route = respx.patch(f"{_GROUPS_URL}/3").mock(
            return_value=httpx.Response(200, json={"data": dict(_GROUP, group_name="platform")})
        )
        group = client.npa.policy.groups.with_response.update_request(
            3, NpaPolicyGroupPatch(group_name="platform")
        ).parse()
        assert route.calls.last.request.method == "PATCH"
        assert sent_json(route) == {"group_name": "platform"}
        assert group.group_name == "platform"

    def test_update_request_rejects_a_patch_with_no_changes(self, client: NetskopeClient) -> None:
        with pytest.raises(ValueError, match="At least one policy group field"):
            NpaPolicyGroupPatch()

    @respx.mock
    async def test_async_get(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(f"{_GROUPS_URL}/3").mock(return_value=httpx.Response(200, json={"data": _GROUP}))
        response = await aclient.npa.policy.groups.with_response.get(3)
        assert response.parse().group_id == "3"

    @respx.mock
    async def test_async_update_request(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.patch(f"{_GROUPS_URL}/3").mock(
            return_value=httpx.Response(200, json={"data": dict(_GROUP, group_name="platform")})
        )
        response = await aclient.npa.policy.groups.with_response.update_request(
            3, NpaPolicyGroupPatch(group_name="platform")
        )
        assert sent_json(route) == {"group_name": "platform"}
        assert response.parse().group_name == "platform"
