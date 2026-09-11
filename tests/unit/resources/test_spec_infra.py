"""Wire conformance for the infrastructure, steering, policy and profile slice.

Every test here pins one difference between what the SDK put on the wire (or
read back off it) and what ``api-gateway-endpoints`` declares, citing the spec
file and line the shape comes from.  Response fixtures are the spec's own
example values wherever it publishes them.

The tenant is ``example.goskope.com``; nothing here reaches a live tenant.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dns import DnsProfileCreate, DnsProfilePatch
from netskope.models.infrastructure import (
    PUBLISHER_UPGRADE_TIMEZONES,
    IPSecTunnel,
    LocalBroker,
    Pop,
    PublisherUpgradeProfile,
)
from netskope.models.private_apps import PrivateApp
from netskope.models.publishers import (
    Publisher,
    PublisherAlertsConfiguration,
    PublisherAlertsConfigurationPatch,
    PublisherApp,
    PublisherRelease,
    PublisherStatus,
)
from netskope.models.steering import IPSecTunnelCreate
from netskope.models.url_lists import UrlList
from tests.unit.resources.conftest import sent_json

_BASE = "https://example.goskope.com"
_PUBLISHERS_URL = f"{_BASE}/api/v2/infrastructure/publishers"
_APPS_URL = f"{_BASE}/api/v2/steering/apps/private"
_URLLIST_URL = f"{_BASE}/api/v2/policy/urllist"
_DNS_URL = f"{_BASE}/api/v2/profiles/dns"
_NAME_VALIDATION_URL = f"{_BASE}/api/v2/infrastructure/npa/namevalidation"
_GLOBALCONFIG_URL = f"{_BASE}/api/v2/steering/globalconfig"


@pytest.fixture
def spec_client() -> Iterator[NetskopeClient]:
    """A sync client against the spec-example tenant, closed after the test."""
    with NetskopeClient(tenant="example.goskope.com", api_token="tok") as client:
        yield client


@pytest.fixture
async def spec_aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """An async client against the spec-example tenant, closed after the test."""
    async with AsyncNetskopeClient(tenant="example.goskope.com", api_token="tok") as client:
        yield client


def _params(route: respx.Route) -> dict[str, str]:
    return dict(route.calls.last.request.url.params)


# --- publishers --------------------------------------------------------------


@respx.mock
def test_publisher_create_sends_the_lbrokerconnect_key(spec_client: NetskopeClient) -> None:
    """publisher_post_request names the flag ``lbrokerconnect``.

    Spec: npa_publishers.yaml:323-326 (post), :354 (patch), :368 (put).  The
    SDK sent ``lbroker_connect``, which the gateway drops, so the flag never
    took effect on any create.
    """
    route = respx.post(_PUBLISHERS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "npa_publisher_1"}})
    )
    spec_client.publishers.create("npa_publisher_1", lbroker_connect=True)

    body = sent_json(route)
    assert body == {"name": "npa_publisher_1", "lbrokerconnect": True}
    assert "lbroker_connect" not in body


@respx.mock
def test_publisher_update_renames_an_extra_lbroker_connect_field(
    spec_client: NetskopeClient,
) -> None:
    """publisher_patch_request carries the same ``lbrokerconnect`` key (npa_publishers.yaml:354)."""
    route = respx.patch(f"{_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "pub01.local"}})
    )
    spec_client.publishers.update(6, name="pub01.local", extra_fields={"lbroker_connect": False})

    assert sent_json(route) == {"name": "pub01.local", "lbrokerconnect": False}


@respx.mock
def test_publisher_bulk_upgrade_sends_string_ids(spec_client: NetskopeClient) -> None:
    """publishers_bulk_request.publishers.id.items is {type: string}.

    Spec: npa_publishers.yaml:294-299, with the endpoint's own examples at
    :1230-1244 sending ``["12"]``.
    """
    route = respx.put(f"{_PUBLISHERS_URL}/bulk").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    spec_client.publishers.bulk_upgrade([12, 15])

    assert sent_json(route) == {
        "publishers": {"apply": {"upgrade_request": True}, "id": ["12", "15"]}
    }


@respx.mock
def test_publisher_alerts_put_carries_selected_users(spec_client: NetskopeClient) -> None:
    """publishers_alert_put_request requires all three keys.

    Spec: npa_publishers.yaml:589-594 for the required set and :627-629 for
    ``selectedUsers``, a comma-joined string.  The SDK could not send it at all.
    """
    route = respx.put(f"{_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    spec_client.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com", "admin2@abc.com"],
        event_types=["CONNECTION_FAILED", "UPGRADE_STARTED"],
        selected_users=["abc@xyz.com", "def@xyz.com"],
    )

    assert sent_json(route) == {
        "adminUsers": ["admin1@abc.com", "admin2@abc.com"],
        "eventTypes": ["CONNECTION_FAILED", "UPGRADE_STARTED"],
        "selectedUsers": "abc@xyz.com,def@xyz.com",
    }


@respx.mock
@pytest.mark.parametrize("event_types", [[], ["UPGRADE_FAILED"] * 6])
def test_publisher_alerts_put_bounds_event_types(
    spec_client: NetskopeClient, event_types: list[str]
) -> None:
    """eventTypes carries minItems: 1 / maxItems: 5 (npa_publishers.yaml:624-625)."""
    with pytest.raises(ValidationError, match="between 1 and 5"):
        spec_client.publishers.update_alerts_configuration(event_types=event_types)
    assert len(respx.calls) == 0


def test_publisher_alerts_request_model_bounds_event_types() -> None:
    """The typed path enforces the same 1..5 bound (npa_publishers.yaml:624-625)."""
    PublisherAlertsConfigurationPatch(event_types=["UPGRADE_FAILED"])
    with pytest.raises(PydanticValidationError, match="at most 5"):
        PublisherAlertsConfigurationPatch(event_types=["UPGRADE_FAILED"] * 6)
    with pytest.raises(PydanticValidationError, match="at least 1"):
        PublisherAlertsConfigurationPatch(event_types=[])


def test_publisher_alerts_response_reads_selected_users() -> None:
    """publishers_alert_get_response.data declares selectedUsers (npa_publishers.yaml:580-582)."""
    config = PublisherAlertsConfiguration.model_validate(
        {
            "adminUsers": ["admin1@abc.com"],
            "eventTypes": ["CONNECTION_FAILED"],
            "selectedUsers": "abc@xyz.com,def@xyz.com",
        }
    )
    assert config.selected_users == "abc@xyz.com,def@xyz.com"


@respx.mock
def test_publisher_single_object_envelope_populates_id_and_name(
    spec_client: NetskopeClient,
) -> None:
    """publisher_response.data names the record id/name, not publisher_id/publisher_name.

    Spec: npa_publishers.yaml:477-481 (``id``) and :493-496 (``name``), with
    the same spelling in publisher_bulk_item (:198, :214).  Every get/create/
    update used to parse to ``publisher_id=None``, so the module's own example
    (``create_registration_token(new_pub.publisher_id)``) passed ``None``.
    """
    respx.get(f"{_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "id": 6,
                    "name": "pub01.local",
                    "common_name": "e2eabac9e9f715ff",
                    "lbrokerconnect": False,
                    "registered": True,
                    "status": "connected",
                    "upgrade_request": True,
                },
            },
        )
    )
    publisher = spec_client.publishers.get(6)

    assert (publisher.publisher_id, publisher.publisher_name) == (6, "pub01.local")
    # upgrade_request (:537-539) and lbrokerconnect (:490-492), not the
    # publisher_upgrade_request / lbroker_proxy / sticky_ip_enabled the SDK
    # declared and the spec has nowhere.
    assert publisher.upgrade_request is True
    assert publisher.lbrokerconnect is False
    for absent in ("publisher_upgrade_request", "lbroker_proxy", "sticky_ip_enabled"):
        assert absent not in Publisher.model_fields


def test_publisher_list_item_keeps_its_own_spelling() -> None:
    """publishers_get_response keys the list item publisher_id/publisher_name.

    Spec: npa_publishers.yaml:812-818.  Both spellings must reach the same
    attributes.
    """
    publisher = Publisher.model_validate(
        {"publisher_id": 6, "publisher_name": "pub01.local", "status": "connected"}
    )
    assert (publisher.publisher_id, publisher.publisher_name) == (6, "pub01.local")


def test_publisher_status_enum_matches_the_spec_value() -> None:
    """The enum is exactly [connected, not registered] (npa_publishers.yaml:827-832)."""
    assert PublisherStatus.NOT_REGISTERED.value == "not registered"
    assert {member.value for member in PublisherStatus} == {"connected", "not registered"}


def test_publisher_app_reads_the_publisher_apps_response() -> None:
    """publishers_private_apps_response.data[] names id/name/private_app_protocol.

    Spec: npa_publishers.yaml:33 (``id``), :40 (``name``), :44
    (``private_app_protocol``), :30 (``host``).  Against those keys every
    record used to parse to all-``None``.
    """
    app = PublisherApp.model_validate(
        {
            "id": 3,
            "name": "[Web-Management]",
            "host": "192.168.1.1",
            "private_app_protocol": "https",
            "protocols": [{"port": "443", "transport": "tcp"}],
        }
    )
    assert (app.app_id, app.app_name, app.host) == (3, "[Web-Management]", "192.168.1.1")
    assert app.protocol == "https"


def test_publisher_release_declares_only_the_spec_fields() -> None:
    """release_item declares docker_tag, name and version (npa_publishers.yaml:950-961)."""
    assert set(PublisherRelease.model_fields) == {"version", "docker_tag", "release_type"}
    release = PublisherRelease.model_validate(
        {"docker_tag": "8690", "name": "Latest", "version": "117.0.0.8690"}
    )
    assert release.release_type == "Latest"


# --- local brokers and upgrade profiles --------------------------------------


def test_local_broker_declares_only_the_spec_fields() -> None:
    """lbroker_response.data has no status and no publisher_id.

    Spec: npa_lbrokers.yaml:139-183 (single) and :192-242 (list item).
    """
    assert "status" not in LocalBroker.model_fields
    assert "publisher_id" not in LocalBroker.model_fields
    broker = LocalBroker.model_validate(
        {"id": 4, "name": "broker-1", "common_name": "abc", "registered": True}
    )
    assert broker.name == "broker-1"


def test_upgrade_profile_create_response_supplies_external_id() -> None:
    """publisher_upgrade_profile_response.data carries the external id under ``id``.

    Spec: npa_upgrade_profiles.yaml:674-678; the schema has no ``external_id``
    at all, while the get-by-id response (:206-272) and list item (:279-350)
    carry both.  ``create()`` used to hand back ``external_id=None``, which the
    module example passes straight to ``assign()``.
    """
    created = PublisherUpgradeProfile.model_validate(
        {
            "id": 10,
            "name": "My Upgrade Profile",
            "docker_tag": "8690",
            "frequency": "0 0 1 * TUE",
            "timezone": "US/Eastern",
            "release_type": "Latest",
            "enabled": True,
        }
    )
    assert created.external_id == 10

    listed = PublisherUpgradeProfile.model_validate({"id": 3, "external_id": 10})
    assert (listed.id, listed.external_id) == (3, 10)


@respx.mock
def test_upgrade_profile_create_rejects_an_unlisted_timezone(spec_client: NetskopeClient) -> None:
    """timezone is a closed 69-value enum (npa_upgrade_profiles.yaml:428-497, :573-650)."""
    assert len(PUBLISHER_UPGRADE_TIMEZONES) == 69
    assert "US/Eastern" in PUBLISHER_UPGRADE_TIMEZONES
    with pytest.raises(ValidationError, match="Invalid timezone"):
        spec_client.npa.upgrade_profiles.create(
            "My Upgrade Profile",
            docker_tag="8690",
            frequency="0 0 1 * TUE",
            timezone="Mars/Olympus_Mons",
            release_type="Latest",
        )
    assert len(respx.calls) == 0


# --- private apps ------------------------------------------------------------


@respx.mock
def test_private_app_filters_become_one_query_expression(spec_client: NetskopeClient) -> None:
    """listNPAPrivateApps declares fields, query, offset and limit — nothing else.

    Spec: npa_apps_private.yaml:490-524 for the parameters, and
    npa_generic.yaml:495-504 for the columns and operators each filter renders
    as.  ``in_policy`` and ``reachable`` take ``yes``/``no`` there, while
    ``clientless_access`` takes ``true``/``false``.
    """
    route = respx.get(_APPS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"private_apps": []}, "total": 0})
    )
    spec_client.private_apps.with_response.list_page(
        app_name="testName", in_policy=True, clientless_access=True, limit=5, offset=0
    )

    assert _params(route) == {
        "query": "name sw testName and in_policy eq yes and clientless_access eq true",
        "limit": "5",
        "offset": "0",
    }


@respx.mock
def test_private_app_list_keeps_a_caller_supplied_query_first(
    spec_client: NetskopeClient,
) -> None:
    """The spec's own multi-filter example is ``name sw test and clientless_access eq true``.

    Spec: npa_apps_private.yaml:509-510.
    """
    route = respx.get(_APPS_URL).mock(
        return_value=httpx.Response(200, json={"data": {"private_apps": []}, "total": 0})
    )
    list(spec_client.private_apps.list(query="name sw test", host="10.0.0.5"))

    assert _params(route)["query"] == "name sw test and host eq 10.0.0.5"


def test_private_app_reads_port_from_its_protocol_entries() -> None:
    """private_apps_item has no top-level port; the port lives in protocols[].

    Spec: npa_apps_private.yaml:133-231 for the item and :180-183 →
    protocol_response_item:402-422 for the protocol entry that carries ``port``.
    ``app.port`` was always ``None``, including in the module's own example.
    """
    app = PrivateApp.model_validate(
        {
            "app_id": 3,
            "app_name": "[Web-Management]",
            "host": "192.168.1.1",
            "protocols": [
                {"port": "443", "transport": "tcp"},
                {"port": "8443", "transport": "tcp"},
            ],
        }
    )
    assert app.port == "443,8443"


def test_private_app_reads_service_publisher_assignments() -> None:
    """The response names the assignments service_publisher_assignments, plural.

    Spec: npa_apps_private.yaml:201-204 →
    service_publisher_assignment_item (npa_publishers.yaml:962-991).  The SDK
    declared a scalar ``service_publisher_assignment`` and a ``publishers``
    array, neither of which the response carries; ``publishers`` now reads the
    assignments so existing callers see real data.
    """
    assignments = [{"primary": True, "publisher_external_id": 1, "publisher_name": "pub01.local"}]
    app = PrivateApp.model_validate({"app_id": 3, "service_publisher_assignments": assignments})
    assert app.service_publisher_assignments == assignments
    assert app.publishers == assignments
    assert "service_publisher_assignment" not in PrivateApp.model_fields


@respx.mock
def test_npa_search_private_apps_populates_id_and_name(spec_client: NetskopeClient) -> None:
    """NPA search answers with private_apps_response_item, which names the record id/name.

    Spec: npa_generic.yaml:70-117 for the item and :536-539 for the envelope
    that carries it, against the ``app_id``/``app_name`` of the steering list
    item (npa_apps_private.yaml:139-145).  Both spellings must land on the same
    attributes or every search hit parses to all-``None``.
    """
    respx.get(f"{_BASE}/api/v2/infrastructure/npa/search/private_apps").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total": 1,
                "data": {"private_apps": [{"id": 3, "name": "testName", "host": "192.168.1.1"}]},
            },
        )
    )
    page = spec_client.npa.with_response.search_private_apps("name sw testName").parse()

    assert [(app.app_id, app.app_name) for app in page.items] == [(3, "testName")]


@respx.mock
def test_npa_search_publishers_reads_the_list_spelling(spec_client: NetskopeClient) -> None:
    """publishers_response_item keeps publisher_id/publisher_name (npa_generic.yaml:125-165)."""
    respx.get(f"{_BASE}/api/v2/infrastructure/npa/search/publishers").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total": 1,
                "data": {
                    "publishers": [
                        {
                            "publisher_id": 6,
                            "publisher_name": "pub01.local",
                            "status": "not registered",
                            "upgrade_request": False,
                            "lbrokerconnect": True,
                        }
                    ]
                },
            },
        )
    )
    page = spec_client.npa.with_response.search_publishers("name sw pub").parse()

    publisher = page.items[0]
    assert (publisher.publisher_id, publisher.publisher_name) == (6, "pub01.local")
    assert publisher.status == PublisherStatus.NOT_REGISTERED


# --- NPA name validation -----------------------------------------------------


@respx.mock
def test_validate_name_sends_tag_type_for_tags(spec_client: NetskopeClient) -> None:
    """tag_type is required for resourceType tag (npa_generic.yaml:282-292).

    Its enum is the strings ``"1"`` (private app) and ``"2"`` (publisher).
    """
    route = respx.get(_NAME_VALIDATION_URL).mock(
        return_value=httpx.Response(
            200, json={"status": "success", "data": {"is_valid_name": True}}
        )
    )
    spec_client.npa.validate_name("tag", "SSH", tag_type=1)

    assert _params(route) == {"resourceType": "tag", "name": "SSH", "tag_type": "1"}


@respx.mock
def test_validate_name_refuses_a_tag_without_its_type(spec_client: NetskopeClient) -> None:
    """A tag name cannot be validated without tag_type (npa_generic.yaml:282-292)."""
    with pytest.raises(ValidationError, match="tag_type is required"):
        spec_client.npa.validate_name("tag", "SSH")
    with pytest.raises(ValidationError, match="Invalid tag_type"):
        spec_client.npa.validate_name("tag", "SSH", tag_type="3")
    assert len(respx.calls) == 0


@respx.mock
def test_validate_name_omits_tag_type_for_other_resources(spec_client: NetskopeClient) -> None:
    """tag_type is "required only for resourceType tag" (npa_generic.yaml:282-284)."""
    route = respx.get(_NAME_VALIDATION_URL).mock(
        return_value=httpx.Response(200, json={"status": "success", "data": {}})
    )
    result = spec_client.npa.with_response.validate_name("private_app", "SSH")

    assert _params(route) == {"resourceType": "private_app", "name": "SSH"}
    # validate_name_response marks nothing required (npa_generic.yaml:188-199).
    assert result.parse().is_valid_name is None


# --- NPA policy --------------------------------------------------------------


@respx.mock
def test_policy_rule_create_sends_group_id_as_a_string(spec_client: NetskopeClient) -> None:
    """npa_policy_request.group_id is {type: string, example: "1"}.

    Spec: policy/npa_policy.yaml:11-13.  The typed path already cast it; the
    untyped ``rules.create()`` helper sent the integer through unchanged.
    """
    route = respx.post(f"{_BASE}/api/v2/policy/npa/rules").mock(
        return_value=httpx.Response(200, json={"data": {"rule_id": 1, "rule_name": "vantest"}})
    )
    spec_client.npa.policy.rules.create(
        rule_name="vantest",
        group_id=1,
        enabled=True,
        rule_data={"policy_type": "private-app", "privateApps": ["app1"]},
    )

    body = sent_json(route)
    assert body["group_id"] == "1"
    assert body["enabled"] == "1"


# --- steering ----------------------------------------------------------------


@respx.mock
@pytest.mark.parametrize("scope", ["nsc", "ztna"])
def test_steering_rejects_scopes_the_spec_has_no_path_for(
    spec_client: NetskopeClient, scope: str
) -> None:
    """npa_global_config.yaml declares six paths, none of them nsc or ztna.

    Spec: /globalconfig (:80), /globalconfig/metadata (:172),
    /globalconfig/clientconfiguration/npa (:218) and its metadata (:307),
    /globalconfig/publishers (:352) and its metadata (:441).
    """
    with pytest.raises(ValidationError, match="npa, publishers"):
        spec_client.steering.with_response.get_config(scope)
    assert len(respx.calls) == 0


@respx.mock
def test_steering_keeps_the_two_scopes_the_spec_declares(spec_client: NetskopeClient) -> None:
    """npa routes under clientconfiguration (:218); publishers does not (:352)."""
    npa = respx.get(f"{_GLOBALCONFIG_URL}/clientconfiguration/npa").mock(
        return_value=httpx.Response(200, json={"data": {"flag": 1}})
    )
    publishers = respx.get(f"{_GLOBALCONFIG_URL}/publishers").mock(
        return_value=httpx.Response(200, json={"data": {"flag": 0}})
    )
    spec_client.steering.get_config("npa")
    spec_client.steering.get_config("publishers")

    assert (npa.call_count, publishers.call_count) == (1, 1)


@respx.mock
def test_ipsec_create_accepts_a_bandwidth_outside_the_usual_tiers(
    spec_client: NetskopeClient,
) -> None:
    """ipsec_tunnel_request_post puts no enum on bandwidth or encryption.

    Spec: steering/ipsec.yaml:237-238 (``bandwidth: integer``) and :241-242
    (``encryption: string``).  A tenant on a tier outside the usual set could
    not use the SDK at all.
    """
    route = respx.post(f"{_BASE}/api/v2/steering/ipsec/tunnels").mock(
        return_value=httpx.Response(200, json={"result": {"id": 1, "site": "IPSec site1"}})
    )
    spec_client.steering.create_tunnel(
        "IPSec site1",
        ["stl1"],
        "psk",
        "5.NE_2_59f18ccc",
        bandwidth=500,
        encryption="AES192-GCM",
    )

    body = sent_json(route)
    assert body["bandwidth"] == 500
    assert body["encryption"] == "AES192-GCM"
    # The request key is ``enable`` (steering/ipsec.yaml:239-240).
    assert body["enable"] is True


def test_ipsec_request_model_accepts_the_same_range() -> None:
    """The typed path matches the untyped one (steering/ipsec.yaml:237-242)."""
    request = IPSecTunnelCreate(
        site="IPSec site1",
        pops=["stl1"],
        psk="psk",
        srcidentity="5.NE_2_59f18ccc",
        bandwidth=500,
        encryption="AES192-GCM",
    )
    assert (request.bandwidth, request.encryption) == (500, "AES192-GCM")
    with pytest.raises(PydanticValidationError, match="greater than 0"):
        IPSecTunnelCreate(
            site="s", pops=["p"], psk="k", srcidentity="i", bandwidth=0, encryption="x"
        )


def test_ipsec_tunnel_model_reads_the_result_item() -> None:
    """ipsec_tunnel_result_item declares enabled and an array of pop objects.

    Spec: steering/ipsec.yaml:318-379, with pops (:355-358) referencing
    ipsec_tunnel_pop_result_item (:158-183).  The SDK declared name, source_ip,
    destination_ip, status, pop and proto, none of which appear there.
    """
    tunnel = IPSecTunnel.model_validate(
        {
            "bandwidth": 50,
            "enabled": True,
            "encryption": "AES128-CBC",
            "id": 1,
            "notes": "Customer managed site",
            "pops": [{"gateway": "163.116.247.38", "name": "stl1", "primary": True}],
            "site": "IPSec site1",
            "srcidentity": "5.NE_2_59f18ccc",
            "vendor": "Default",
            "version": 2,
        }
    )
    assert (tunnel.id, tunnel.site, tunnel.enabled) == (1, "IPSec site1", True)
    assert tunnel.pops is not None and tunnel.pops[0]["name"] == "stl1"
    for absent in ("name", "source_ip", "destination_ip", "status", "pop", "proto"):
        assert absent not in IPSecTunnel.model_fields


def test_pop_model_reads_the_pop_result_item() -> None:
    """ipsec_pop_result_item has no country and no address list.

    Spec: steering/ipsec.yaml:28-81; ``country`` exists only as a query
    parameter on GET /ipsec/pops (:408-415).
    """
    pop = Pop.model_validate(
        {
            "acceptingtunnels": True,
            "bandwidth": "1000",
            "gateway": "163.116.247.38",
            "id": "1",
            "location": "Saint Louis",
            "name": "stl1",
            "probeip": "10.137.22.216",
            "region": "US",
        }
    )
    assert (pop.name, pop.region, pop.gateway) == ("stl1", "US", "163.116.247.38")
    assert "country" not in Pop.model_fields
    assert "ip_addresses" not in Pop.model_fields


# --- DNS profiles ------------------------------------------------------------


@respx.mock
def test_dns_deploy_all_is_a_query_parameter(spec_client: NetskopeClient) -> None:
    """``all`` is declared ``in: query`` on POST /dns/deploy.

    Spec: profiles/dns.yaml:1874-1883.  Sent in the body it both missed the
    flag and produced a body with neither of DNSDeployRequest's required keys
    (:1328-1332).
    """
    route = respx.post(f"{_DNS_URL}/deploy").mock(
        return_value=httpx.Response(200, json={"profiles": []})
    )
    spec_client.dns.deploy(all=True, change_note="Deploy DNS Profiles")

    assert _params(route) == {"all": "true"}
    assert sent_json(route) == {"change_note": "Deploy DNS Profiles"}


@respx.mock
def test_dns_deploy_ids_sends_the_required_body(spec_client: NetskopeClient) -> None:
    """DNSDeployRequest declares required: [change_note, ids] with string ids.

    Spec: profiles/dns.yaml:1328-1344.
    """
    route = respx.post(f"{_DNS_URL}/deploy").mock(
        return_value=httpx.Response(200, json={"profiles": []})
    )
    spec_client.dns.deploy(
        ids=["69c0661d-3e5d-49d6-88ee-3c1390955004"], change_note="Deploy DNS Profiles"
    )

    assert _params(route) == {}
    assert sent_json(route) == {
        "ids": ["69c0661d-3e5d-49d6-88ee-3c1390955004"],
        "change_note": "Deploy DNS Profiles",
    }


@respx.mock
def test_dns_inheritance_group_deploy_leaves_change_note_optional(
    spec_client: NetskopeClient,
) -> None:
    """InheritanceGroupDeployRequest requires only ids (profiles/dns.yaml:1345-1348)."""
    route = respx.post(f"{_DNS_URL}/inheritancegroups/deploy").mock(
        return_value=httpx.Response(200, json={"inheritancegroups": []})
    )
    spec_client.dns.inheritance_groups.deploy(ids=["49c0661d-3e5d-49d6-88ee-3c1390955004"])

    assert sent_json(route) == {"ids": ["49c0661d-3e5d-49d6-88ee-3c1390955004"]}


@respx.mock
def test_dns_update_sends_the_log_traffic_mode(spec_client: NetskopeClient) -> None:
    """DNSProfileUpdateRequest.log_traffic is enum [Blocked DNS, All DNS].

    Spec: profiles/dns.yaml:852-856, and :560-565 for the create request.  The
    resource parameter was a bool, so every call sent a value the gateway
    rejects.
    """
    route = respx.patch(f"{_DNS_URL}/547c581b-b779-4770-8b73-aeece0742252").mock(
        return_value=httpx.Response(200, json={"name": "My Profile"})
    )
    spec_client.dns.update(
        "547c581b-b779-4770-8b73-aeece0742252", log_traffic="Blocked DNS", interactive=False
    )

    assert sent_json(route) == {"log_traffic": "Blocked DNS"}
    assert _params(route) == {"interactive": "false"}


@respx.mock
def test_dns_writes_default_to_pending(spec_client: NetskopeClient) -> None:
    """``interactive`` decides whether a write deploys itself.

    Spec: POST /dns (profiles/dns.yaml:1504-1513) and PATCH /dns/{id}
    (:1732-1741).  The gateway's own default is false — "created and deployed"
    (:1566-1567) — so the SDK, which never sent the parameter, wrote straight
    to the live tenant and left ``deploy()`` with nothing of its own to apply.
    """
    create = respx.post(_DNS_URL).mock(
        return_value=httpx.Response(202, json={"id": "547c581b", "name": "My Profile"})
    )
    spec_client.dns.create("My Profile")

    assert _params(create) == {"interactive": "true"}
    assert sent_json(create) == {"name": "My Profile"}


@respx.mock
async def test_dns_typed_writes_carry_interactive(spec_aclient: AsyncNetskopeClient) -> None:
    """The typed accessors send the same parameter (profiles/dns.yaml:1504-1513, :1732-1741)."""
    create = respx.post(_DNS_URL).mock(
        return_value=httpx.Response(202, json={"id": "547c581b", "name": "My Profile"})
    )
    await spec_aclient.dns.with_response.create(DnsProfileCreate(name="My Profile"))
    assert _params(create) == {"interactive": "true"}

    update = respx.patch(f"{_DNS_URL}/547c581b").mock(
        return_value=httpx.Response(200, json={"id": "547c581b", "name": "Renamed"})
    )
    await spec_aclient.dns.with_response.update(
        "547c581b", DnsProfilePatch(name="Renamed"), interactive=False
    )
    assert _params(update) == {"interactive": "false"}


# --- URL lists ---------------------------------------------------------------


@respx.mock
def test_url_list_deploy_posts_to_urllist_deploy(spec_client: NetskopeClient) -> None:
    """The only URL-list deploy operation is POST /urllist/deploy.

    Spec: policy/urllist.yaml:201-227.  No bare ``/deploy`` path exists in the
    spec, so ``POST /api/v2/policy/deploy`` was a 404 on every call.
    """
    record: dict[str, Any] = {
        "id": 42,
        "name": "Block",
        "data": {"type": "exact", "urls": ["www.test.com"]},
        "modify_by": "Netskope API",
        "modify_type": "Created",
        "pending": 0,
    }
    route = respx.post(f"{_URLLIST_URL}/deploy").mock(
        return_value=httpx.Response(200, json=[record])
    )
    deployed = spec_client.url_lists.with_response.deploy().parse()

    assert route.calls.last.request.url.path == "/api/v2/policy/urllist/deploy"
    # The deploy response is an array of Urllist (policy/urllist.yaml:209-217).
    assert [item.id for item in deployed.urllists] == [42]


@respx.mock
def test_url_list_listing_sends_the_two_declared_filters(spec_client: NetskopeClient) -> None:
    """GET /urllist accepts pending (0|1) and field, singular.

    Spec: policy/urllist.yaml:133-142 and :143-156.
    """
    route = respx.get(_URLLIST_URL).mock(return_value=httpx.Response(200, json=[]))
    list(spec_client.url_lists.list(pending=1, field="name"))

    params = _params(route)
    assert params["pending"] == "1"
    assert params["field"] == "name"

    with pytest.raises(ValidationError, match="pending must be"):
        list(spec_client.url_lists.list(pending=2))
    with pytest.raises(ValidationError, match="field must be"):
        list(spec_client.url_lists.list(field="urls"))


def test_url_list_pending_is_an_integer() -> None:
    """Urllist.pending is {type: integer} (policy/urllist.yaml:119-120).

    A boolean field coerced 0/1 and raised on anything else.
    """
    assert UrlList.model_validate({"id": 1, "pending": 2}).pending == 2
    assert UrlList.model_validate({"id": 1, "pending": 1}).pending == 1
    for absent in ("count", "json_version"):
        assert absent not in UrlList.model_fields
