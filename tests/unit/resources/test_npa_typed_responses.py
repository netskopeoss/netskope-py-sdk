"""NPA typed response contracts, at the real HTTP boundary."""

from __future__ import annotations

import inspect

import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import NetskopeError, ResponseValidationError, ValidationError
from netskope.models.infrastructure import LocalBrokerCreate, LocalBrokerPatch, UpgradeProfileUpdate
from netskope.models.npa_policy import NpaPolicyGroupCreate, NpaPolicyRuleCreate, NpaPolicyRulePatch
from netskope.models.private_apps import (
    PrivateAppCreate,
    PrivateAppDiscoveryRequest,
    PrivateAppPatch,
)
from netskope.models.publishers import PublisherAlertsConfigurationPatch
from netskope.models.steering import IPSecTunnelCreate, IPSecTunnelPatch, SteeringSettings
from tests.unit.resources.conftest import sent_json

BASE = "https://t.goskope.com/api/v2"
PROFILE = {
    "id": 4,
    "name": "weekly",
    "enabled": False,
    "docker_tag": "123",
    "frequency": "0 2 * * 0",
    "timezone": "US/Pacific",
    "release_type": "Latest",
}

READS = [
    (
        "steering/apps/private",
        lambda c: c.private_apps.with_response.list_page(limit=2, offset=0),
        {
            "data": {"private_apps": [{"app_id": "007", "app_name": "app", "future": [1]}]},
            "total": 9,
        },
    ),
    (
        "steering/apps/private/tags",
        lambda c: c.private_apps.tags.with_response.list_page(limit=2, offset=0),
        {"data": {"tags": [{"id": "007", "tag_name": "tag", "future": [1]}]}, "total": 9},
    ),
    (
        "policy/npa/rules",
        lambda c: c.npa.policy.rules.with_response.list_page(limit=2, offset=0),
        {"data": {"rules": [{"rule_id": "007", "enabled": "1", "future": [1]}]}, "total": 9},
    ),
    (
        "policy/npa/policygroups",
        lambda c: c.npa.policy.groups.with_response.list_page(limit=2, offset=0),
        {"data": {"policygroups": [{"group_id": "007", "future": [1]}]}, "total": 9},
    ),
    (
        "steering/ipsec/tunnels",
        lambda c: c.steering.with_response.list_tunnels_page(limit=2, offset=0),
        {"result": [{"id": "007", "future": [1]}], "total": 9},
    ),
    (
        "steering/ipsec/pops",
        lambda c: c.steering.with_response.list_pops_page(limit=2, offset=0),
        {"result": [{"name": "us", "future": [1]}], "total": 9},
    ),
    (
        "policy/urllist",
        lambda c: c.url_lists.with_response.list_page(limit=2, offset=0),
        {
            "data": {
                "urllists": [
                    {
                        "id": "007",
                        "name": "urls",
                        "data": {"urls": [], "type": "exact"},
                        "future": [1],
                    }
                ]
            },
            "total": 1,
        },
    ),
]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("path,invoke,body", READS)
@respx.mock
async def test_one_bounded_page_preserves_typed_items_and_wire_values(
    client,
    aclient,
    asynchronous,
    path,
    invoke,
    body,
):
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    response = invoke(aclient if asynchronous else client)
    if inspect.isawaitable(response):
        response = await response
    page = response.parse()
    assert page.total == body["total"]
    assert page.has_more is (path != "policy/urllist")
    assert page.limit == 2 and page.offset == 0
    assert len(page.items) == 1
    assert page.items[0].model_extra["future"] == [1]
    assert response.json() == body
    assert route.call_count == 1
    # ``GET /policy/urllist`` declares only ``pending`` and ``field``
    # (policy/urllist.yaml:132-156), so its window is applied locally and no
    # paging parameters reach the wire.
    expected = {} if path == "policy/urllist" else {"limit": "2", "offset": "0"}
    assert dict(route.calls[0].request.url.params) == expected


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("path,invoke,body", READS)
@respx.mock
async def test_malformed_pages_are_not_silently_empty(
    client, aclient, asynchronous, path, invoke, body
):
    route = respx.get(f"{BASE}/{path}").respond(200, json={"data": "not-a-collection"})
    response = invoke(aclient if asynchronous else client)
    if inspect.isawaitable(response):
        response = await response
    with pytest.raises(ResponseValidationError):
        response.parse()
    assert route.call_count == 1


# Single-resource and unpaginated reads: (path, params, invoke, body, check).
ITEM_READS = [
    (
        "infrastructure/npa/namevalidation",
        {"resourceType": "private_app", "name": "ssh"},
        lambda c: c.npa.with_response.validate_name("private_app", "ssh"),
        {"data": {"valid": True, "message": "available"}},
        lambda parsed: parsed.is_valid_name is True and parsed.message == "available",
    ),
    (
        "infrastructure/npa/search/publishers",
        {"query": "name sw prod"},
        lambda c: c.npa.with_response.search_publishers("name sw prod"),
        {"data": {"publishers": [{"publisher_id": "7", "publisher_name": "prod-1"}]}, "total": 1},
        lambda parsed: parsed.total == 1 and parsed.items[0].publisher_name == "prod-1",
    ),
    (
        "infrastructure/npa/search/private_apps",
        {"query": "name sw ssh"},
        lambda c: c.npa.with_response.search_private_apps("name sw ssh"),
        {"data": {"private_apps": [{"app_id": "5", "app_name": "ssh"}]}, "total": 1},
        lambda parsed: parsed.total == 1 and parsed.items[0].app_id == 5,
    ),
    (
        "steering/globalconfig/clientconfiguration/npa",
        {},
        lambda c: c.steering.with_response.get_config("npa"),
        {"data": {"flag_a": 1}},
        lambda parsed: parsed.data == {"flag_a": 1},
    ),
    (
        "steering/ipsec/tunnels/1",
        {},
        lambda c: c.steering.with_response.get_tunnel(1),
        {"data": {"id": 1, "site": "dc", "bandwidth": 250, "future": [1]}},
        lambda parsed: parsed.bandwidth == 250 and parsed.model_extra["future"] == [1],
    ),
    (
        "infrastructure/lbrokers",
        {},
        lambda c: c.npa.local_brokers.with_response.list(),
        {"data": [{"id": "10", "name": "dc1", "future": [1]}], "status": "success"},
        lambda parsed: [broker.id for broker in parsed] == [10],
    ),
    (
        "infrastructure/lbrokers/10",
        {},
        lambda c: c.npa.local_brokers.with_response.get(10),
        {"data": {"id": 10, "name": "dc1", "registered": True}},
        lambda parsed: parsed.name == "dc1" and parsed.registered is True,
    ),
    (
        "infrastructure/lbrokers/brokerconfig",
        {},
        lambda c: c.npa.local_brokers.with_response.get_config(),
        {"data": {"hostname": "broker.example.com"}},
        lambda parsed: parsed.hostname == "broker.example.com",
    ),
    (
        "infrastructure/publisherupgradeprofiles",
        {},
        lambda c: c.npa.upgrade_profiles.with_response.list(),
        {"data": {"upgrade_profiles": [PROFILE]}, "status": "success"},
        lambda parsed: [profile.name for profile in parsed] == ["weekly"],
    ),
    (
        "infrastructure/publisherupgradeprofiles/4",
        {},
        lambda c: c.npa.upgrade_profiles.with_response.get(4),
        {"data": PROFILE},
        lambda parsed: parsed.id == 4 and parsed.enabled is False,
    ),
]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("path,params,invoke,body,check", ITEM_READS)
@respx.mock
async def test_single_request_typed_reads(
    client, aclient, asynchronous, path, params, invoke, body, check
):
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    response = invoke(aclient if asynchronous else client)
    if inspect.isawaitable(response):
        response = await response
    assert check(response.parse())
    assert response.json() == body
    assert route.call_count == 1
    assert len(respx.calls) == 1
    assert dict(route.calls[0].request.url.params) == params


WRITES = [
    (
        "POST",
        "steering/apps/private",
        lambda c: c.private_apps.with_response.create_request(
            PrivateAppCreate.model_validate(
                {
                    "app_name": "ssh",
                    "host": "10.0.0.1",
                    "protocols": [{"type": "tcp", "port": "22"}],
                    "publishers": [{"publisher_id": "7"}],
                }
            )
        ),
        {
            "app_name": "ssh",
            "host": "10.0.0.1",
            "protocols": [{"type": "tcp", "port": "22"}],
            "publishers": [{"publisher_id": "7"}],
        },
        {"data": {"app_id": 1, "future": 1}},
    ),
    (
        "PATCH",
        "steering/apps/private/1",
        lambda c: c.private_apps.with_response.update_request(
            1, PrivateAppPatch(clientless_access=False)
        ),
        {"clientless_access": False},
        {"data": {"app_id": 1}},
    ),
    (
        "POST",
        "infrastructure/lbrokers",
        lambda c: c.npa.local_brokers.with_response.create_request(
            LocalBrokerCreate(name="dc", city="Austin")
        ),
        {"name": "dc", "city_name": "Austin"},
        {"data": {"id": 1}},
    ),
    (
        "PUT",
        "infrastructure/lbrokers/1",
        lambda c: c.npa.local_brokers.with_response.update_request(
            1, LocalBrokerPatch(city="Austin")
        ),
        {"city_name": "Austin"},
        {"data": {"id": 1}},
    ),
    (
        "PUT",
        "infrastructure/publisherupgradeprofiles/4",
        lambda c: c.npa.upgrade_profiles.with_response.update_request(
            4, UpgradeProfileUpdate.model_validate(PROFILE)
        ),
        PROFILE,
        {"data": PROFILE},
    ),
    (
        "POST",
        "policy/npa/rules",
        lambda c: c.npa.policy.rules.with_response.create_request(
            NpaPolicyRuleCreate.model_validate(
                {
                    "rule_name": "ssh",
                    "enabled": False,
                    "group_id": 5,
                    "rule_data": {
                        "privateApps": ["ssh"],
                        "match_criteria_action": {"action_name": "allow"},
                    },
                }
            )
        ),
        {
            "rule_name": "ssh",
            "enabled": "0",
            "group_id": "5",
            "rule_data": {
                "privateApps": ["ssh"],
                "match_criteria_action": {"action_name": "allow"},
            },
        },
        {"data": {"rule_id": 1, "enabled": "0"}},
    ),
    (
        "PATCH",
        "policy/npa/rules/1",
        lambda c: c.npa.policy.rules.with_response.update_request(
            1, NpaPolicyRulePatch(enabled=False)
        ),
        {"enabled": "0"},
        {"data": {"rule_id": 1}},
    ),
    (
        "POST",
        "policy/npa/policygroups",
        lambda c: c.npa.policy.groups.with_response.create_request(
            NpaPolicyGroupCreate.model_validate(
                {
                    "group_name": "eng",
                    "group_order": {"group_id": "5", "order": "after"},
                }
            )
        ),
        {"group_name": "eng", "group_order": {"group_id": "5", "order": "after"}},
        {"data": {"group_id": "6"}},
    ),
    (
        "POST",
        "steering/ipsec/tunnels",
        lambda c: c.steering.with_response.create_tunnel_request(
            IPSecTunnelCreate(
                site="dc",
                pops=["US"],
                psk="secret",
                srcidentity="dc.test",
                enabled=False,
            )
        ),
        {"site": "dc", "pops": ["US"], "psk": "secret", "srcidentity": "dc.test", "enable": False},
        {"result": {"id": 1, "enabled": False}},
    ),
    (
        "PATCH",
        "steering/ipsec/tunnels/1",
        lambda c: c.steering.with_response.update_tunnel_request(
            1, IPSecTunnelPatch(enabled=False)
        ),
        {"enable": False},
        {"result": {"id": 1}},
    ),
    (
        "PUT",
        "infrastructure/publishers/alertsconfiguration",
        # All three keys are ``required`` on this PUT (npa_publishers.yaml:591-594),
        # and its 200 carries only ``status`` (:630-638).
        lambda c: c.publishers.with_response.update_alerts_configuration_request(
            PublisherAlertsConfigurationPatch(
                admin_users=["admin@example.com"],
                event_types=["UPGRADE_FAILED"],
                selected_users="admin@example.com",
            )
        ),
        {
            "adminUsers": ["admin@example.com"],
            "eventTypes": ["UPGRADE_FAILED"],
            "selectedUsers": "admin@example.com",
        },
        {"status": "success"},
    ),
    (
        "POST",
        "steering/apps/private/discoverysettings",
        lambda c: c.private_apps.with_response.update_discovery_settings(
            PrivateAppDiscoveryRequest.model_validate(
                {"settings": {"status": "DISABLED", "users": []}}
            )
        ),
        {"settings": {"status": "DISABLED", "users": []}},
        {"data": {"settings": {"status": "DISABLED"}}},
    ),
]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method,path,invoke,payload,body", WRITES)
@respx.mock
async def test_single_request_typed_writes(
    client, aclient, asynchronous, method, path, invoke, payload, body
):
    route = respx.request(method, f"{BASE}/{path}").respond(200, json=body)
    response = invoke(aclient if asynchronous else client)
    if inspect.isawaitable(response):
        response = await response
    response.parse()
    assert response.json() == body
    assert route.call_count == 1
    assert len(respx.calls) == 1
    assert sent_json(route) == payload


# Mutations whose request body is fixed by their arguments, not a request model.
KEYWORD_WRITES = [
    (
        "PATCH",
        "steering/globalconfig/clientconfiguration/npa",
        lambda c: c.steering.with_response.update_config_request(
            "npa", SteeringSettings({"flag_a": 1})
        ),
        {"flag_a": 1},
        # The PATCH 200 declares only ``status`` (npa_global_config.yaml:274-283).
        {"status": "success"},
        lambda parsed: parsed.status == "success",
    ),
    (
        "PUT",
        "infrastructure/lbrokers/brokerconfig",
        lambda c: c.npa.local_brokers.with_response.update_config("broker.example.com"),
        {"hostname": "broker.example.com"},
        {"data": {"hostname": "broker.example.com"}},
        lambda parsed: parsed.hostname == "broker.example.com",
    ),
    (
        "POST",
        "infrastructure/lbrokers/10/registrationtoken",
        lambda c: c.npa.local_brokers.with_response.create_registration_token(10),
        None,
        {"data": {"token": "reg-token"}},
        lambda parsed: parsed == "reg-token",
    ),
    (
        "PUT",
        "infrastructure/publisherupgradeprofiles/bulk",
        lambda c: c.npa.upgrade_profiles.with_response.assign(4, [10, 20]),
        {"publishers": {"apply": {"publisher_upgrade_profiles_id": "4"}, "id": ["10", "20"]}},
        # publisher_upgrade_profile_bulk_response (npa_upgrade_profiles.yaml:186-205).
        {"data": {"publishers": [{"id": 10}, {"id": 20}]}, "status": "success", "total": 2},
        lambda parsed: (
            parsed.status == "success"
            and parsed.total == 2
            and [pub.publisher_id for pub in parsed.publishers] == [10, 20]
        ),
    ),
]

ALL_WRITES = [(*write, None) for write in WRITES] + KEYWORD_WRITES


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method,path,invoke,payload,body,check", KEYWORD_WRITES)
@respx.mock
async def test_keyword_writes_send_canonical_bodies(
    client, aclient, asynchronous, method, path, invoke, payload, body, check
):
    route = respx.request(method, f"{BASE}/{path}").respond(200, json=body)
    response = invoke(aclient if asynchronous else client)
    if inspect.isawaitable(response):
        response = await response
    assert check(response.parse())
    assert route.call_count == 1
    assert len(respx.calls) == 1
    if payload is None:
        assert route.calls[0].request.content == b""
    else:
        assert sent_json(route) == payload


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("method,path,invoke,payload,body,check", ALL_WRITES)
@respx.mock
async def test_mutations_do_not_retry_server_failures(
    client, aclient, asynchronous, method, path, invoke, payload, body, check
):
    route = respx.request(method, f"{BASE}/{path}").respond(503, json={"message": "unavailable"})
    with pytest.raises(NetskopeError):
        result = invoke(aclient if asynchronous else client)
        if inspect.isawaitable(result):
            await result
    assert route.call_count == 1


@pytest.mark.parametrize(
    "request_model,values",
    [
        (PrivateAppPatch, {"unknown": True}),
        (PrivateAppPatch, {"host": None}),
        (IPSecTunnelPatch, {"enabled": None}),
        (IPSecTunnelPatch, {"bandwidth": 100.0}),
        (IPSecTunnelPatch, {}),
        (LocalBrokerPatch, {"name": "rename"}),
        (LocalBrokerPatch, {"latitude": 91}),
        (LocalBrokerPatch, {"custom_public_ip": "not-an-ip"}),
        (UpgradeProfileUpdate, {"id": 4, "name": "incomplete"}),
        (NpaPolicyRuleCreate, {"rule_name": "unscoped", "rule_data": {}}),
        (NpaPolicyGroupCreate, {"group_name": "missing-anchor"}),
        (PublisherAlertsConfigurationPatch, {"eventTypes": ["unknown"]}),
        (SteeringSettings, {"option": True}),
    ],
)
def test_invalid_requests_are_rejected(request_model, values):
    with pytest.raises(ModelValidationError):
        request_model.model_validate(values)


@respx.mock
def test_nested_request_mutation_is_revalidated(client):
    request = PrivateAppCreate.model_validate(
        {
            "app_name": "ssh",
            "host": "internal",
            "protocols": [{"type": "tcp", "port": "22"}],
        }
    )
    request.protocols.append({"type": "sctp", "port": "22"})
    with pytest.raises(ValidationError):
        client.private_apps.with_response.create_request(request)
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_full_profile_id_must_match_request(client, aclient, asynchronous):
    request = UpgradeProfileUpdate.model_validate(PROFILE)
    with pytest.raises(ValidationError, match="match"):
        result = (
            aclient if asynchronous else client
        ).npa.upgrade_profiles.with_response.update_request(8, request)
        if inspect.isawaitable(result):
            await result
    assert len(respx.calls) == 0


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_string_ids_for_association_and_policy_check(client, aclient, asynchronous):
    sdk = aclient if asynchronous else client
    route = respx.patch(f"{BASE}/steering/apps/private/publishers").respond(
        200, json={"data": [{"app_id": 1}]}
    )
    result = sdk.private_apps.with_response.add_publishers([1], [2])
    if inspect.isawaitable(result):
        result = await result
    assert result.parse()[0].app_id == 1
    assert sent_json(route) == {"private_app_ids": ["1"], "publisher_ids": ["2"]}
    check = respx.post(f"{BASE}/steering/apps/private/tags/getpolicyinuse").respond(
        200,
        json={"data": [{"tag_id": "1", "num_in_use": "2", "policy_in_use": "p1,p2"}]},
    )
    result = sdk.private_apps.tags.with_response.get_policy_in_use([1])
    if inspect.isawaitable(result):
        result = await result
    assert result.parse().data[0].num_in_use == "2"
    assert sent_json(check) == {"ids": ["1"]}


@respx.mock
def test_url_list_update_preserves_existing_two_request_workflow(client):
    old = {"id": 1, "name": "old", "data": {"urls": ["example.com"], "type": "regex"}}
    respx.get(f"{BASE}/policy/urllist/1").respond(200, json=old)
    route = respx.put(f"{BASE}/policy/urllist/1").respond(200, json={**old, "name": "new"})
    result = client.url_lists.with_response.update(1, name="new")
    assert result.parse().urls == ["example.com"]
    assert sent_json(route) == {"name": "new", "data": {"urls": ["example.com"], "type": "regex"}}
    assert len(respx.calls) == 2


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("list_type", ["glob", ""])
@respx.mock
async def test_url_list_invalid_type_fails_before_lookup(client, aclient, asynchronous, list_type):
    sdk = aclient if asynchronous else client
    with pytest.raises(ValidationError):
        result = sdk.url_lists.with_response.update(1, list_type=list_type)
        if inspect.isawaitable(result):
            await result
    assert len(respx.calls) == 0
