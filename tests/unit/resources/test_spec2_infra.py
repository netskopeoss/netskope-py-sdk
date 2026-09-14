"""SPEC2 conformance for the infrastructure / steering / policy / profile slice.

Every test pins one fix from the second spec-conformance review and cites the
``api-gateway-endpoints`` ``production/endpoints`` file and line the shape comes
from.  Nothing here reaches a live tenant: the synthetic host
``example.goskope.coken`` is only reachable through ``allow_custom_tenant=True``
and every request is intercepted by ``respx.mock``, whose default router carries
``assert_all_mocked=True`` (pinned by
:func:`test_the_mock_router_refuses_an_unmocked_request`), so a request this
module did not declare fails the test instead of leaving the process.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dns import DnsDeployment, DnsInheritanceGroupDeployment, DnsReference
from netskope.models.infrastructure import UpgradeProfileAssignment
from netskope.models.private_apps import PrivateApp
from netskope.models.publishers import (
    PublisherActionResult,
    PublisherAlertsConfigurationStatus,
)
from netskope.models.steering import SteeringConfigStatus
from netskope.models.url_lists import UrlList
from tests.unit.resources.conftest import drain, sent_json

_TENANT = "example.goskope.coken"
_BASE = f"https://{_TENANT}"
_PUBLISHERS_URL = f"{_BASE}/api/v2/infrastructure/publishers"
_LBROKERS_URL = f"{_BASE}/api/v2/infrastructure/lbrokers"
_PROFILES_URL = f"{_BASE}/api/v2/infrastructure/publisherupgradeprofiles"
_APPS_URL = f"{_BASE}/api/v2/steering/apps/private"
_TUNNELS_URL = f"{_BASE}/api/v2/steering/ipsec/tunnels"
_POPS_URL = f"{_BASE}/api/v2/steering/ipsec/pops"
_NPA_CONFIG_URL = f"{_BASE}/api/v2/steering/globalconfig/clientconfiguration/npa"
_DNS_URL = f"{_BASE}/api/v2/profiles/dns"
_URLLIST_URL = f"{_BASE}/api/v2/policy/urllist"

# An id that would retarget the request at a sibling contract path.
_TRAVERSING_IDS = ("../tags", "7/../../publishers", "3/../pops", "..")


def test_the_mock_router_refuses_an_unmocked_request() -> None:
    """No test here can reach a live tenant: an undeclared request is an error."""
    assert respx.mock._assert_all_mocked is True


@pytest.fixture
def sclient() -> Iterator[NetskopeClient]:
    """A sync client against the synthetic host, closed after the test."""
    with NetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=0,
    ) as client:
        yield client


@pytest.fixture
async def saclient() -> AsyncIterator[AsyncNetskopeClient]:
    """An async client against the synthetic host, closed after the test."""
    async with AsyncNetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=0,
    ) as client:
        yield client


@pytest.fixture
def retrying() -> Iterator[NetskopeClient]:
    """A sync client that would replay a request the SDK marks replay-safe."""
    with NetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=3,
        backoff_factor=0,
    ) as client:
        yield client


# --- SPEC2-INFRA-1: path ids are validated at every interpolation site --------
#
# Every one of these path parameters is declared as an integer:
#   private_app_id  steering/npa_apps_private.yaml:759-766 (format: int32)
#   id (tunnel)     steering/ipsec.yaml:789-798
#   id (lbroker)    infrastructure/npa_lbrokers.yaml:425-435
#   external_id     infrastructure/npa_upgrade_profiles.yaml:886-894
#   publisher_id    infrastructure/npa_publishers.yaml:1358-1366
# so a crafted string id cannot describe any of them, and interpolating one
# unchecked sends the request to a different, sometimes destructive, path.


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
    sclient: NetskopeClient, bad_id: str
) -> None:
    """A crafted id is refused instead of retargeting the request (see citations above)."""
    for call in _sync_id_calls(sclient, bad_id):
        with pytest.raises(ValidationError, match="Invalid"):
            call()
    assert len(respx.calls) == 0


@pytest.mark.parametrize("bad_id", _TRAVERSING_IDS)
@respx.mock
async def test_async_legacy_path_ids_are_validated_before_any_request(
    saclient: AsyncNetskopeClient, bad_id: str
) -> None:
    """The async mirrors validate the same ids at the same sites."""
    for call in _async_id_calls(saclient, bad_id):
        with pytest.raises(ValidationError, match="Invalid"):
            await call()
    assert len(respx.calls) == 0


@respx.mock
def test_well_formed_integer_ids_still_reach_their_declared_path(
    sclient: NetskopeClient,
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

    assert sclient.private_apps.get(7).app_id == 7
    sclient.steering.delete_tunnel(3)
    assert sclient.npa.local_brokers.get(11).id == 11
    sclient.npa.upgrade_profiles.delete(5)
    sclient.publishers.delete(6)

    assert all(route.call_count == 1 for route in (app, tunnel, broker, profile, publisher))


# --- SPEC2-INFRA-2: writes send every property their operation requires -------


@respx.mock
def test_publisher_patch_requires_the_declared_name(sclient: NetskopeClient) -> None:
    """``publisher_patch_request`` declares ``required: [name]``.

    Spec: infrastructure/npa_publishers.yaml:338-341, for
    ``PATCH /publishers/{publisher_id}``.  A body that changed only
    ``lbrokerconnect`` was reported as a success the gateway had rejected.
    """
    with pytest.raises(ValidationError, match="requires name"):
        sclient.publishers.update(6, extra_fields={"lbroker_connect": True})
    assert len(respx.calls) == 0

    route = respx.patch(f"{_PUBLISHERS_URL}/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "name": "pub"}})
    )
    sclient.publishers.update(6, name="pub", extra_fields={"lbroker_connect": True})
    assert sent_json(route) == {"name": "pub", "lbrokerconnect": True}


@respx.mock
async def test_async_publisher_patch_requires_the_declared_name(
    saclient: AsyncNetskopeClient,
) -> None:
    """The async mirror enforces the same ``required: [name]`` (:338-341)."""
    with pytest.raises(ValidationError, match="requires name"):
        await saclient.publishers.update(6, extra_fields={"lbroker_connect": True})
    assert len(respx.calls) == 0


@respx.mock
def test_alerts_put_sends_all_three_required_keys(sclient: NetskopeClient) -> None:
    """``publishers_alert_put_request.required`` is all three keys.

    Spec: infrastructure/npa_publishers.yaml:591-594 for the required set,
    :624-625 for the 1..5 ``eventTypes`` bound and :627-629 for
    ``selectedUsers`` as one comma-joined string.  A no-argument call used to
    send ``{}`` to a three-required-property schema and report success.
    """
    with pytest.raises(ValidationError, match="requires admin_users, event_types, selected_users"):
        sclient.publishers.update_alerts_configuration()
    assert len(respx.calls) == 0

    route = respx.put(f"{_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    sclient.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com"],
        event_types=["UPGRADE_FAILED"],
        selected_users=["abc@xyz.com", "def@xyz.com"],
    )
    assert sent_json(route) == {
        "adminUsers": ["admin1@abc.com"],
        "eventTypes": ["UPGRADE_FAILED"],
        "selectedUsers": "abc@xyz.com,def@xyz.com",
    }


# --- SPEC2-INFRA-3: the policy-in-use POSTs are not replay-safe ---------------
#
# ``POST /apps/private/getpolicyinuse`` declares ``rbac.access: rw``
# (steering/npa_apps_private.yaml:735-740) and
# ``POST /apps/private/tags/getpolicyinuse`` the same
# (steering/npa_private_tag.yaml:487-492), so neither is replayable however
# read-sounding its name.


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("getpolicyinuse", lambda c: c.private_apps.get_policy_in_use([7])),
        ("tags/getpolicyinuse", lambda c: c.private_apps.tags.get_policy_in_use([7])),
        ("getpolicyinuse", lambda c: c.private_apps.with_response.get_policy_in_use([7])),
        (
            "tags/getpolicyinuse",
            lambda c: c.private_apps.tags.with_response.get_policy_in_use([7]),
        ),
    ],
)
@respx.mock
def test_policy_in_use_posts_are_not_retried(
    retrying: NetskopeClient, path: str, invoke: Any
) -> None:
    """A 503 is surfaced after exactly one attempt, not replayed."""
    route = respx.post(f"{_APPS_URL}/{path}").mock(return_value=httpx.Response(503))
    with pytest.raises(Exception, match="5"):
        invoke(retrying)
    assert route.call_count == 1


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("getpolicyinuse", lambda c: c.private_apps.get_policy_in_use([7])),
        ("tags/getpolicyinuse", lambda c: c.private_apps.tags.get_policy_in_use([7])),
        ("getpolicyinuse", lambda c: c.private_apps.with_response.get_policy_in_use([7])),
        (
            "tags/getpolicyinuse",
            lambda c: c.private_apps.tags.with_response.get_policy_in_use([7]),
        ),
    ],
)
@respx.mock
async def test_async_policy_in_use_posts_are_not_retried(path: str, invoke: Any) -> None:
    """The async mirrors of all four sites are equally unreplayable."""
    route = respx.post(f"{_APPS_URL}/{path}").mock(return_value=httpx.Response(503))
    async with AsyncNetskopeClient(
        tenant=_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=3,
        backoff_factor=0,
    ) as client:
        with pytest.raises(Exception, match="5"):
            await invoke(client)
    assert route.call_count == 1


# --- SPEC2-INFRA-4: typed writes describe the payload their operation returns -


@respx.mock
def test_dns_deploy_returns_the_declared_profile_list(sclient: NetskopeClient) -> None:
    """``POST /dns/deploy`` 200 is ``DNSProfileList``, not an acknowledgment.

    Spec: profiles/dns.yaml:1891-1896 references ``DNSProfileList`` (:217-226),
    i.e. ``{total, profiles}``; the response carries no ``status`` at all, so an
    acknowledgment type reported ``status=None`` and left the profiles reachable
    only through ``model_extra``.
    """
    body = {"profiles": [{"id": "p1", "name": "Policy"}, {"id": "p2"}], "total": 2}
    route = respx.post(f"{_DNS_URL}/deploy").mock(return_value=httpx.Response(200, json=body))
    page = sclient.dns.with_response.deploy(
        DnsDeployment(ids=["p1", "p2"], change_note="Approved")
    ).parse()

    assert [profile.id for profile in page.items] == ["p1", "p2"]
    assert page.total == 2
    assert route.call_count == 1


@respx.mock
async def test_dns_group_deploy_returns_the_declared_group_list(
    saclient: AsyncNetskopeClient,
) -> None:
    """``POST /dns/inheritancegroups/deploy`` 200 is ``InheritanceGroupList``.

    Spec: profiles/dns.yaml:2384-2389 references ``InheritanceGroupList``
    (:1135-1144), i.e. ``{total, inheritancegroups}``.
    """
    body = {"inheritancegroups": [{"id": "g1", "name": "Group"}], "total": 1}
    route = respx.post(f"{_DNS_URL}/inheritancegroups/deploy").mock(
        return_value=httpx.Response(200, json=body)
    )
    response = await saclient.dns.inheritance_groups.with_response.deploy(
        DnsInheritanceGroupDeployment(ids=["g1"])
    )
    page = response.parse()

    assert [group.id for group in page.items] == ["g1"]
    assert page.total == 1
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_url_list_delete_returns_the_deleted_record(
    sclient: NetskopeClient, saclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """``DELETE /urllist/{id}`` 200 is ``DeletedUrllist``, a full URL-list record.

    Spec: policy/urllist.yaml:276-281 references ``DeletedUrllist`` (:3-35),
    which declares ``data``, ``id``, ``modify_by``, ``modify_time``,
    ``modify_type``, ``name`` and ``pending``; no deployment status.
    """
    body = {
        "id": 5,
        "name": "l1",
        "data": {"urls": ["bad.com"], "type": "exact"},
        "modify_type": "Deleted",
        "pending": 1,
    }
    route = respx.delete(f"{_URLLIST_URL}/5").mock(return_value=httpx.Response(200, json=body))
    accessor = (saclient if asynchronous else sclient).url_lists.with_response
    response = accessor.delete(5)
    if asynchronous:
        response = await response
    record = response.parse()

    assert isinstance(record, UrlList)
    assert (record.id, record.name, record.modify_type, record.pending) == (
        5,
        "l1",
        "Deleted",
        1,
    )
    assert record.urls == ["bad.com"]
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_remove_publishers_returns_the_declared_private_apps(
    sclient: NetskopeClient, saclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """``DELETE /apps/private/publishers`` 200 is ``{data: [...], status}``.

    Spec: steering/npa_private_publisher.yaml:167-178, whose ``data`` items are
    ``private_apps_response_item``; byte-identical to the PATCH (:193-...) and
    PUT on the same path, which the SDK already decodes as ``list[PrivateApp]``.
    """
    body = {
        "data": [{"id": 2, "name": "private_app_name", "host": "abc.com"}],
        "status": "success",
    }
    route = respx.delete(f"{_APPS_URL}/publishers").mock(
        return_value=httpx.Response(200, json=body)
    )
    accessor = (saclient if asynchronous else sclient).private_apps.with_response
    response = accessor.remove_publishers([2], [4, 5])
    if asynchronous:
        response = await response
    apps = response.parse()

    assert apps is not None
    assert all(isinstance(app, PrivateApp) for app in apps)
    assert [(app.app_id, app.app_name, app.host) for app in apps] == [
        (2, "private_app_name", "abc.com")
    ]
    assert sent_json(route) == {"private_app_ids": ["2"], "publisher_ids": ["4", "5"]}


@respx.mock
def test_bulk_publisher_writes_keep_their_publisher_records(sclient: NetskopeClient) -> None:
    """Both bulk envelopes carry their records under ``data.publishers``.

    Spec: ``publishers_bulk_response``
    (infrastructure/npa_publishers.yaml:639-702) and
    ``publisher_upgrade_profile_bulk_response``
    (infrastructure/npa_upgrade_profiles.yaml:186-205).  Descending into
    ``data`` before validating discarded the records the operations return.
    """
    upgrade = respx.put(f"{_PUBLISHERS_URL}/bulk").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"publishers": [{"id": 12, "name": "pub12"}]}, "status": "success"},
        )
    )
    action = sclient.publishers.with_response.bulk_upgrade([12]).parse()
    assert isinstance(action, PublisherActionResult)
    assert action.status == "success"
    assert [pub.publisher_id for pub in action.publishers] == [12]
    assert upgrade.call_count == 1

    assign = respx.put(f"{_PROFILES_URL}/bulk").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"publishers": [{"id": 10}, {"id": 20}]},
                "status": "success",
                "total": 2,
            },
        )
    )
    assignment = sclient.npa.upgrade_profiles.with_response.assign(5, [10, 20]).parse()
    assert isinstance(assignment, UpgradeProfileAssignment)
    assert (assignment.status, assignment.total) == ("success", 2)
    assert [pub.publisher_id for pub in assignment.publishers] == [10, 20]
    assert assign.call_count == 1


def test_upgrade_profile_assignment_declares_no_invented_fields() -> None:
    """``publisher_upgrade_profile_bulk_response`` has no ``message``/``updated``.

    Spec: infrastructure/npa_upgrade_profiles.yaml:186-205 declares exactly
    ``data.publishers``, ``status`` and ``total``.
    """
    assert set(UpgradeProfileAssignment.model_fields) == {"status", "total", "publishers"}
    assert set(PublisherActionResult.model_fields) == {"status", "publishers"}


# --- SPEC2-INFRA-5: status-only writes are typed as acknowledgments -----------


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_alerts_put_returns_a_status_acknowledgment(
    sclient: NetskopeClient, saclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """``publishers_alert_put_response`` declares only ``status``.

    Spec: infrastructure/npa_publishers.yaml:630-638, enum
    ``success`` / ``not found`` / ``failure``, referenced from the PUT at
    :1180-1187.  Parsing it into the configuration model produced a hollow
    object indistinguishable from a configuration that really is empty.
    """
    route = respx.put(f"{_PUBLISHERS_URL}/alertsconfiguration").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    client = saclient if asynchronous else sclient
    result = client.publishers.update_alerts_configuration(
        admin_users=["admin1@abc.com"],
        event_types=["UPGRADE_FAILED"],
        selected_users="abc@xyz.com",
    )
    if asynchronous:
        result = await result

    assert isinstance(result, PublisherAlertsConfigurationStatus)
    assert result.status == "success"
    assert not hasattr(result, "admin_users")
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_steering_config_patch_returns_a_status_acknowledgment(
    sclient: NetskopeClient, saclient: AsyncNetskopeClient, asynchronous: bool
) -> None:
    """The global-config PATCH 200 declares only ``status``.

    Spec: steering/npa_global_config.yaml:274-283 for
    ``/globalconfig/clientconfiguration/npa`` and :408-417 for
    ``/globalconfig/publishers``; neither echoes the stored flags, so the old
    return value was an all-default ``SteeringConfig``.
    """
    route = respx.patch(_NPA_CONFIG_URL).mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    client = saclient if asynchronous else sclient
    result = client.steering.update_config("npa", settings={"npa_ff": "1"})
    if asynchronous:
        result = await result

    assert isinstance(result, SteeringConfigStatus)
    assert result.status == "success"
    assert sent_json(route) == {"npa_ff": "1"}


@respx.mock
def test_typed_steering_config_patch_returns_the_acknowledgment(
    sclient: NetskopeClient,
) -> None:
    """The typed accessor reports the same acknowledgment (:274-283)."""
    from netskope.models.steering import SteeringSettings

    respx.patch(_NPA_CONFIG_URL).mock(return_value=httpx.Response(200, json={"status": "success"}))
    parsed = sclient.steering.with_response.update_config_request(
        "npa", SteeringSettings({"npa_ff": 1})
    ).parse()
    assert isinstance(parsed, SteeringConfigStatus)
    assert parsed.status == "success"


# --- SPEC2-INFRA-6: the IPsec list operations bound their declared limit ------


@pytest.mark.parametrize(
    "accessor,url",
    [("list_pops_page", _POPS_URL), ("list_tunnels_page", _TUNNELS_URL)],
)
@respx.mock
def test_ipsec_limit_admits_its_declared_range(
    sclient: NetskopeClient, accessor: str, url: str
) -> None:
    """``limit`` declares ``minimum: 0, maximum: 100``.

    Spec: steering/ipsec.yaml:478-486 for ``GET /ipsec/pops`` and :672-680 for
    ``GET /ipsec/tunnels``; these are the only formal ``maximum:`` values in the
    slice.  An unbounded ``limit`` was spent on a round trip the gateway can
    only reject or silently clamp.
    """
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": [], "total": 0}))
    method = getattr(sclient.steering.with_response, accessor)

    for limit in (0, 100):
        method(limit=limit).parse()
    assert [dict(call.request.url.params)["limit"] for call in route.calls] == ["0", "100"]

    for limit in (101, 1000, -1):
        with pytest.raises(ValidationError, match="limit must be an integer"):
            method(limit=limit)
    assert route.call_count == 2


@pytest.mark.parametrize(
    "accessor,url",
    [("list_pops_page", _POPS_URL), ("list_tunnels_page", _TUNNELS_URL)],
)
@respx.mock
async def test_async_ipsec_limit_admits_its_declared_range(
    saclient: AsyncNetskopeClient, accessor: str, url: str
) -> None:
    """The async accessors enforce the same bounds (ipsec.yaml:478-486, :672-680)."""
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": [], "total": 0}))
    method = getattr(saclient.steering.with_response, accessor)
    (await method(limit=100)).parse()
    with pytest.raises(ValidationError, match="limit must be an integer"):
        await method(limit=101)
    assert route.call_count == 1


@pytest.mark.parametrize("lister", ["list_pops", "list_tunnels"])
@pytest.mark.parametrize("page_size", [0, -1, True])
def test_ipsec_iterators_require_a_positive_page_size(
    sclient: NetskopeClient, lister: str, page_size: Any
) -> None:
    """A page size of 0 is inside the declared ``limit`` range but cannot advance.

    ``limit`` declares ``minimum: 0`` (steering/ipsec.yaml:478-486), which a
    one-page accessor can honour; an offset traversal stepping by 0 would never
    reach the next page, so the iterator requires a positive stride.
    """
    with pytest.raises(ValidationError, match="page_size"):
        getattr(sclient.steering, lister)(page_size=page_size)


@pytest.mark.parametrize("lister,url", [("list_pops", _POPS_URL), ("list_tunnels", _TUNNELS_URL)])
@respx.mock
def test_ipsec_iterators_clamp_to_the_declared_maximum(
    sclient: NetskopeClient, lister: str, url: str
) -> None:
    """A page size above ``maximum: 100`` is clamped rather than sent (:478-486, :672-680)."""
    route = respx.get(url).mock(return_value=httpx.Response(200, json={"result": []}))
    list(getattr(sclient.steering, lister)(page_size=500))
    assert dict(route.calls.last.request.url.params)["limit"] == "100"


# --- SPEC2-INFRA-8: DNS reference records declare nothing required ------------


def test_dns_reference_accepts_a_record_without_a_name() -> None:
    """No DNS reference schema declares a ``required`` block.

    Spec: ``DNSTunnel`` (profiles/dns.yaml:13-27), ``DNSDomainCategory``
    (:38-184) and ``DNSRecordType`` (:195-216) declare ``id`` and ``name`` as
    plain optional properties, so one record without a ``name`` must not reject
    its whole page.  ``DNSDomainCategory`` also declares ``category_type``
    (:179-184).
    """
    assert DnsReference.model_validate({"id": "3"}).name is None
    assert DnsReference.model_validate({"name": "A"}).id is None
    category = DnsReference.model_validate(
        {"id": "123", "name": "Newly Registered Domain", "category_type": "Security"}
    )
    assert category.category_type == "Security"


@respx.mock
def test_dns_reference_page_keeps_a_record_without_a_name(sclient: NetskopeClient) -> None:
    """A nameless record no longer rejects the whole page (profiles/dns.yaml:195-216)."""
    respx.get(f"{_DNS_URL}/recordtypes").mock(
        return_value=httpx.Response(200, json={"recordtypes": [{"id": "3"}], "total": 1})
    )
    page = sclient.dns.with_response.list_record_types().parse()
    assert [record.id for record in page.items] == ["3"]
    assert page.items[0].name is None


# --- SPEC2-INFRA-9: the DNS deletes can stage a deletion ---------------------


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("u-1", lambda c, **kw: c.dns.delete("u-1", **kw)),
        ("inheritancegroups/g1", lambda c, **kw: c.dns.inheritance_groups.delete("g1", **kw)),
    ],
)
@respx.mock
def test_dns_deletes_expose_interactive_at_the_spec_default(
    sclient: NetskopeClient, path: str, invoke: Any
) -> None:
    """``interactive`` is declared on both DELETEs with ``default: false``.

    Spec: profiles/dns.yaml:1811-1820 for ``DELETE /dns/{id}`` and :2302-2311
    for ``DELETE /dns/inheritancegroups/{id}``; 200 means deleted and deployed,
    202 means ``pending-delete``.  The SDK could not stage a deletion at all.
    """
    route = respx.delete(f"{_DNS_URL}/{path}").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    invoke(sclient)
    assert dict(route.calls.last.request.url.params) == {"interactive": "false"}

    invoke(sclient, interactive=True)
    assert dict(route.calls.last.request.url.params) == {"interactive": "true"}
    assert route.call_count == 2


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("u-1", lambda c, **kw: c.dns.delete("u-1", **kw)),
        ("inheritancegroups/g1", lambda c, **kw: c.dns.inheritance_groups.delete("g1", **kw)),
    ],
)
@respx.mock
async def test_async_dns_deletes_expose_interactive(
    saclient: AsyncNetskopeClient, path: str, invoke: Any
) -> None:
    """The async deletes send the same declared query (:1811-1820, :2302-2311)."""
    route = respx.delete(f"{_DNS_URL}/{path}").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    await invoke(saclient, interactive=True)
    assert dict(route.calls.last.request.url.params) == {"interactive": "true"}


@pytest.mark.parametrize(
    "path,invoke",
    [
        ("u-1", lambda c, **kw: c.dns.with_response.delete("u-1", **kw)),
        (
            "inheritancegroups/g1",
            lambda c, **kw: c.dns.inheritance_groups.with_response.delete("g1", **kw),
        ),
    ],
)
@respx.mock
def test_typed_dns_deletes_expose_interactive(
    sclient: NetskopeClient, path: str, invoke: Any
) -> None:
    """The typed deletes carry ``interactive`` too (:1811-1820, :2302-2311)."""
    route = respx.delete(f"{_DNS_URL}/{path}").mock(
        return_value=httpx.Response(202, json={"status": "pending-delete"})
    )
    parsed = invoke(sclient, interactive=True).parse()
    assert parsed is not None
    assert parsed.status == "pending-delete"
    assert dict(route.calls.last.request.url.params) == {"interactive": "true"}


# --- SPEC2-INFRA-10: the legacy steering write validates its flag domain -----


@pytest.mark.parametrize("value", ["yes", 2, "01", None, True])
@respx.mock
def test_legacy_steering_update_rejects_undeclared_flag_values(
    sclient: NetskopeClient, value: Any
) -> None:
    """``global_config_data_request`` admits only ``0`` and ``1``.

    Spec: steering/npa_global_config.yaml:43-52 :
    ``additionalProperties: oneOf [{string, pattern ^[01]$}, {integer, enum [0, 1]}]``.
    The legacy path forwarded the mapping unchecked while the typed path
    validated it.
    """
    with pytest.raises(ValidationError, match=r"must be 0 or 1"):
        sclient.steering.update_config("npa", settings={"npa_ff": value})
    assert len(respx.calls) == 0


@pytest.mark.parametrize("value", ["yes", 2])
@respx.mock
async def test_async_legacy_steering_update_rejects_undeclared_flag_values(
    saclient: AsyncNetskopeClient, value: Any
) -> None:
    """The async mirror applies the same domain (npa_global_config.yaml:43-52)."""
    with pytest.raises(ValidationError, match=r"must be 0 or 1"):
        await saclient.steering.update_config("npa", settings={"npa_ff": value})
    assert len(respx.calls) == 0


@pytest.mark.parametrize("value", [0, 1, "0", "1"])
@respx.mock
def test_legacy_steering_update_sends_the_declared_flag_values(
    sclient: NetskopeClient, value: Any
) -> None:
    """Both declared spellings still reach the wire unchanged (:43-52)."""
    route = respx.patch(_NPA_CONFIG_URL).mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    sclient.steering.update_config("npa", settings={"npa_ff": value})
    assert sent_json(route) == {"npa_ff": value}


# --- SPEC2-INFRA-11: no undeclared pagination parameters are sent ------------
#
# ``GET /infrastructure/publishers`` declares exactly one query parameter,
# ``fields`` (infrastructure/npa_publishers.yaml:1024-1032); its envelope's
# ``total`` (:877-879) reports the size of the collection and does not
# establish an offset window.  ``GET /policy/urllist`` declares exactly
# ``pending`` and ``field`` (policy/urllist.yaml:132-156) and returns a bare
# array with no total (:157-165).


@respx.mock
def test_publisher_list_sends_no_undeclared_parameters(sclient: NetskopeClient) -> None:
    """Only ``fields`` reaches the wire, and the collection is fetched once."""
    body = {
        "data": {"publishers": [{"publisher_id": n} for n in (1, 2, 3, 4, 5)]},
        "total": 5,
        "status": "success",
    }
    route = respx.get(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))

    # A page size smaller than the collection must not make the parser refuse
    # the body or ask for a second page that would re-deliver the same records.
    assert [pub.publisher_id for pub in sclient.publishers.list(page_size=2)] == [1, 2, 3, 4, 5]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params

    page = sclient.publishers.list_page(fields=["publisher_id"], offset=1, limit=2)
    assert [pub.publisher_id for pub in page.items] == [2, 3]
    assert (page.offset, page.limit, page.total, page.has_more) == (1, 2, 5, True)
    assert page.metadata == {"total": 5, "status": "success"}
    assert dict(route.calls.last.request.url.params) == {"fields": "publisher_id"}
    assert route.call_count == 2


@respx.mock
async def test_async_publisher_list_makes_exactly_one_request(
    saclient: AsyncNetskopeClient,
) -> None:
    """The async iterator makes no extra HTTP call for a collection it already holds."""
    body = {"publishers": [{"publisher_id": n} for n in (1, 2, 3)], "total": 3}
    route = respx.get(_PUBLISHERS_URL).mock(return_value=httpx.Response(200, json=body))
    records = await drain(saclient.publishers.list(page_size=1))
    assert [pub.publisher_id for pub in records] == [1, 2, 3]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params


@respx.mock
def test_publisher_list_rejects_the_undeclared_filter(sclient: NetskopeClient) -> None:
    """``filter`` is not declared, so a *filter_expr* is refused, not dropped."""
    for call in (
        lambda: list(sclient.publishers.list(filter_expr="status eq 'connected'")),
        lambda: sclient.publishers.list_page(filter_expr="status eq 'connected'"),
        lambda: sclient.publishers.with_response.list_page(filter_expr="status eq 'connected'"),
    ):
        with pytest.raises(ValidationError, match="filter_expr is not supported"):
            call()
    assert len(respx.calls) == 0


@respx.mock
async def test_async_publisher_list_rejects_the_undeclared_filter(
    saclient: AsyncNetskopeClient,
) -> None:
    """The async accessors refuse it too (npa_publishers.yaml:1024-1032)."""
    with pytest.raises(ValidationError, match="filter_expr is not supported"):
        await drain(saclient.publishers.list(filter_expr="x eq y"))
    with pytest.raises(ValidationError, match="filter_expr is not supported"):
        await saclient.publishers.list_page(filter_expr="x eq y")
    with pytest.raises(ValidationError, match="filter_expr is not supported"):
        await saclient.publishers.with_response.list_page(filter_expr="x eq y")
    assert len(respx.calls) == 0


@respx.mock
def test_url_list_list_sends_only_its_two_declared_parameters(
    sclient: NetskopeClient,
) -> None:
    """``pending`` and ``field`` are the whole declared query (policy/urllist.yaml:132-156)."""
    records = [{"id": n, "name": f"l{n}", "data": {"urls": [], "type": "exact"}} for n in (1, 2, 3)]
    route = respx.get(_URLLIST_URL).mock(return_value=httpx.Response(200, json=records))

    assert [item.id for item in sclient.url_lists.list(pending=1, field="name", page_size=2)] == [
        1,
        2,
        3,
    ]
    assert route.call_count == 1
    assert dict(route.calls.last.request.url.params) == {"pending": "1", "field": "name"}

    page = sclient.url_lists.with_response.list_page(limit=2, offset=1).parse()
    assert [item.id for item in page.items] == [2, 3]
    assert (page.offset, page.limit) == (1, 2)
    assert not route.calls.last.request.url.params


@respx.mock
async def test_async_url_list_list_makes_exactly_one_request(
    saclient: AsyncNetskopeClient,
) -> None:
    """The async iterator holds the whole collection after one request."""
    records = [{"id": n, "name": f"l{n}"} for n in (1, 2, 3)]
    route = respx.get(_URLLIST_URL).mock(return_value=httpx.Response(200, json=records))
    items = await drain(saclient.url_lists.list(page_size=1))
    assert [item.id for item in items] == [1, 2, 3]
    assert route.call_count == 1
    assert not route.calls.last.request.url.params
