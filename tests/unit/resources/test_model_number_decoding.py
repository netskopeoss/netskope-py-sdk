"""A field the contract types as ``number`` decodes without truncation.

Every schema in ``production/endpoints`` that types a field as ``number``
admits a fraction, so the SDK may not quietly floor one: the tests here pin
that across the models that carry such a field, and pin the paths where a
numeric identifier reaches the wire.
"""

from __future__ import annotations

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.administration import AdminRole
from netskope.models.alerts import Alert
from netskope.models.devices import DeviceTag
from netskope.models.events import Event, IncidentEvent, NetworkEvent
from netskope.models.incidents import Incident
from netskope.models.notifications import NotificationDeliverySettings
from netskope.models.rbac import (
    RbacRole,
    RbacRoleApiGroup,
    RbacRoleDetail,
    RbacRoleScope,
    RbacRoleSummary,
    RoleMutationReceipt,
)
from netskope.models.tokens import ApiToken


@pytest.mark.parametrize(
    "model,payload,attribute,expected",
    [
        # events/search_alert.yaml:48-50 (cci), :54-56 (count)
        (Alert, {"cci": 1.5}, "cci", 1.5),
        (Alert, {"count": 2.5}, "count", 2.5),
        # events/search_network.yaml:139-141, :73-75, :88-90
        (NetworkEvent, {"srcport": 1.5}, "src_port", 1.5),
        (NetworkEvent, {"dstport": 2.5}, "dst_port", 2.5),
        (NetworkEvent, {"numbytes": 3.5}, "num_bytes", 3.5),
        # rbac/ms-rbac.yaml:1621-1623 (roleId), :1651-1653 (userCount)
        (RbacRoleSummary, {"roleId": 1.5}, "id", 1.5),
        (RbacRoleSummary, {"userCount": 2.5}, "user_count", 2.5),
        (RbacRole, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2439-2444 and :2529-2534
        (RoleMutationReceipt, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2231-2233
        (RbacRoleDetail, {"roleId": 1.5}, "id", 1.5),
        # rbac/ms-rbac.yaml:2190-2192
        (RbacRoleApiGroup, {"apiGroupId": 1.5}, "api_group_id", 1.5),
        # rbac/ms-rbac.yaml:2040-2042
        (RbacRoleScope, {"scopeFieldId": 1.5}, "scope_field_id", 1.5),
        # auth/api-tokens.yaml:59-61
        (ApiToken, {"expires": 1.5}, "expires", 1.5),
        # devices/tag.yaml:738-741, :749-753, :754-758
        (DeviceTag, {"id": 1.5}, "id", 1.5),
        (DeviceTag, {"device_count": 2.5}, "device_count", 2.5),
        (DeviceTag, {"device_classification_count": 3.5}, "device_classification_count", 3.5),
        # platform/ms-platform.yaml:336-345, value at :338-339
        (AdminRole, {"value": 1.5}, "value", 1.5),
    ],
)
def test_a_declared_number_field_keeps_its_fraction(
    model: type, payload: dict[str, object], attribute: str, expected: float
) -> None:
    assert getattr(model.model_validate(payload), attribute) == expected


@pytest.mark.parametrize(
    "model,payload,attribute",
    [
        (Alert, {"cci": 89}, "cci"),
        (Alert, {"count": 1}, "count"),
        (NetworkEvent, {"srcport": 53}, "src_port"),
        (RbacRoleSummary, {"roleId": 7}, "id"),
        (ApiToken, {"expires": 2147384600}, "expires"),
        (DeviceTag, {"id": 1}, "id"),
        (AdminRole, {"value": 3}, "value"),
    ],
)
def test_an_integral_number_still_decodes_as_int(
    model: type, payload: dict[str, object], attribute: str
) -> None:
    value = getattr(model.model_validate(payload), attribute)
    assert isinstance(value, int) and not isinstance(value, bool)


def test_cci_no_longer_truncates_and_still_reads_the_legacy_shapes() -> None:
    """search_alert.yaml:48-50 types cci as a number; 1.5 is not 1."""
    assert Alert.model_validate({"cci": 1.5}).cci == 1.5
    assert Alert.model_validate({"cci": "8"}).cci == 8
    assert Alert.model_validate({"cci": ""}).cci is None
    assert Alert.model_validate({}).cci is None


async def _role_call(asynchronous, operation):
    client_type = AsyncNetskopeClient if asynchronous else NetskopeClient
    client = client_type(
        tenant="example.goskope.coken", allow_custom_tenant=True, api_token="synthetic"
    )
    try:
        result = operation(client.rbac.roles)
        return await result if asynchronous else result
    finally:
        closed = client.close()
        if asynchronous:
            await closed


@pytest.mark.parametrize("model", [Incident, IncidentEvent])
def test_incident_identifiers_preserve_fractional_numbers(model: type[Incident | IncidentEvent]):
    """events/search_incident.yaml:229-231 declares a number."""
    assert model.model_validate({"incident_id": 1.5}).incident_id == 1.5
    assert model.model_validate({"incident_id": 1}).incident_id == 1
    assert model.model_validate({"incident_id": "legacy-id"}).incident_id == "legacy-id"


def test_notification_timeout_preserves_fractional_seconds():
    """notifications/user-delivery-settings.yaml:10-14 is a number."""
    settings = NotificationDeliverySettings.model_validate(
        {
            "cloudAppsDeliveryMethod": "client",
            "webTrafficDeliveryMethod": "browser",
            "notificationTimeout": 60.5,
        }
    )
    assert settings.notification_timeout == 60.5


@pytest.mark.parametrize("value", [29, 29.0, 29.5])
def test_event_identifiers_accept_every_declared_number(value: int | float):
    """SPEC2-VERIFY-ID-2: events/search_app.yaml:123-125 declares id as number."""
    assert Event.model_validate({"id": value}).id == str(value)


def test_fractional_insertion_time_does_not_reject_an_incident_page():
    """SPEC2-VERIFY-ID-1: events/search_incident.yaml:265-267 declares number."""
    with (
        respx.mock(assert_all_mocked=True) as router,
        NetskopeClient(
            tenant="example.goskope.coken", allow_custom_tenant=True, api_token="synthetic"
        ) as client,
    ):
        router.get("https://example.goskope.coken/api/v2/events/datasearch/incident").respond(
            200,
            json={"result": [{"_id": "aa", "ns_insertion_epoch_timestamp": 1719475700.5}]},
        )
        response = client.events.with_response.list_page("incident", limit=1)
        assert response.parse().items[0].insertion_epoch_timestamp == 1719475700.5


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_role_creation_fetches_the_exact_numeric_identifier(asynchronous):
    """ms-rbac.yaml:2442-2443 and :1195-1200 both declare number."""
    url = "https://example.goskope.coken/api/v2/rbac/roles"
    with respx.mock(assert_all_mocked=True) as router:
        created = router.post(url).respond(200, json={"roleId": 1.5})
        fetched = router.get(f"{url}/1.5").respond(
            200, json={"roleId": 1.5, "roleName": "fractional"}
        )
        role = await _role_call(asynchronous, lambda roles: roles.create("fractional"))
        assert role.id == 1.5
        assert created.call_count == fetched.call_count == 1
        assert len(router.calls) == 2


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("typed", [False, True])
async def test_role_detail_preserves_a_fractional_path_identifier(asynchronous, typed):
    """ms-rbac.yaml:1195-1200 permits fractional numeric path IDs."""
    with respx.mock(assert_all_mocked=True) as router:
        route = router.get("https://example.goskope.coken/api/v2/rbac/roles/1.5").respond(
            200, json={"roleId": 1.5, "roleName": "fractional"}
        )
        result = await _role_call(
            asynchronous,
            lambda roles: (roles.with_response if typed else roles).get_detail(1.5),
        )
        role = result.parse() if typed else result
        assert role.id == 1.5
        assert route.call_count == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.5])
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_numeric_role_paths_keep_the_finite_nonnegative_sdk_rule(value, asynchronous):
    """Wider number support does not weaken the SDK's own ID checks."""
    with respx.mock(assert_all_mocked=True) as router:
        with pytest.raises(ValidationError):
            await _role_call(asynchronous, lambda roles: roles.get(value))
        assert not router.calls
