"""Legal response numbers found by the second review's field sweep."""

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.events import Event, IncidentEvent
from netskope.models.incidents import Incident
from netskope.models.notifications import NotificationDeliverySettings


@pytest.mark.parametrize("model", [Incident, IncidentEvent])
def test_incident_identifiers_preserve_fractional_numbers(model: type[Incident | IncidentEvent]):
    """SPEC2-MODEL-1: events/search_incident.yaml:229-231 declares a number."""
    assert model.model_validate({"incident_id": 1.5}).incident_id == 1.5
    assert model.model_validate({"incident_id": 1}).incident_id == 1
    assert model.model_validate({"incident_id": "legacy-id"}).incident_id == "legacy-id"


def test_notification_timeout_preserves_fractional_seconds():
    """SPEC2-MODEL-1: notifications/user-delivery-settings.yaml:10-14 is a number."""
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


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_role_creation_fetches_the_exact_numeric_identifier(asynchronous):
    """SPEC2-ID-7: ms-rbac.yaml:2442-2443 and :1195-1200 both declare number."""
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
    """SPEC2-ID-7: ms-rbac.yaml:1195-1200 permits fractional numeric path IDs."""
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
    """SPEC2-ID-7: extend number support without weakening the SDK's ID checks."""
    with respx.mock(assert_all_mocked=True) as router:
        with pytest.raises(ValidationError):
            await _role_call(asynchronous, lambda roles: roles.get(value))
        assert not router.calls
