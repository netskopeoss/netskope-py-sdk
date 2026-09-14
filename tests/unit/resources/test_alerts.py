"""Tests for client.alerts with mocked HTTP."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.alerts import Alert
from netskope.models.events import Event
from netskope.models.incidents import Incident

_ALERTS_URL = "https://t.goskope.com/api/v2/events/datasearch/alert"


class TestAlertsResource:
    """Tests for client.alerts."""

    @respx.mock
    def test_list_returns_alerts(self, client: NetskopeClient) -> None:
        respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [
                        {"_id": "a1", "alert_name": "Test Alert", "severity_level": "high"},
                        {"_id": "a2", "alert_name": "Alert 2", "severity_level": "low"},
                    ],
                    "status": {"total": 2},
                },
            )
        )
        alerts = list(client.alerts.list())
        assert len(alerts) == 2
        assert isinstance(alerts[0], Alert)
        assert alerts[0].alert_name == "Test Alert"

    @respx.mock
    def test_list_with_query(self, client: NetskopeClient) -> None:
        route = respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        list(client.alerts.list(query='severity eq "high"'))
        url = str(route.calls[0].request.url)
        assert "query=" in url

    @respx.mock
    def test_get_alert(self, client: NetskopeClient) -> None:
        respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "abc", "alert_name": "Found"}],
                },
            )
        )
        alert = client.alerts.get("abc")
        assert alert.id == "abc"
        assert alert.alert_name == "Found"

    @respx.mock
    def test_get_alert_not_found(self, client: NetskopeClient) -> None:
        respx.get(_ALERTS_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(NotFoundError):
            client.alerts.get("deadbeef")

    @respx.mock
    @pytest.mark.parametrize("alert_id", ["not-hex", "xyz", "abc 123", "../etc"])
    def test_get_rejects_non_hex_id_no_http(self, client: NetskopeClient, alert_id: str) -> None:
        """Alert ids are hex strings; anything else fails before any HTTP call."""
        with pytest.raises(ValidationError):
            client.alerts.get(alert_id)
        assert len(respx.calls) == 0

    @respx.mock
    def test_list_sends_groupbys_and_combined_orderbys(self, client: NetskopeClient) -> None:
        """search_alert.yaml:351-368 names these groupbys and orderbys; no sortby exists."""
        route = respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        list(client.alerts.list(group_by="alert_type", order_by="timestamp"))
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "alert_type"
        assert "groupby" not in params
        assert params["orderbys"] == "timestamp DESC"
        assert "sortby" not in params and "sortorder" not in params
        assert params["timeout"] == "180"

    @respx.mock
    def test_list_groupbys_joins_list_and_ascending_sort(self, client: NetskopeClient) -> None:
        route = respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        list(
            client.alerts.list(
                group_by=["alert_type", "user"], order_by="timestamp", descending=False
            )
        )
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "alert_type,user"
        assert params["orderbys"] == "timestamp ASC"
        assert "sortby" not in params


class TestAsyncAlertsResource:
    """Tests for aclient.alerts."""

    @respx.mock
    async def test_get_rejects_non_hex_id_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.alerts.get("not-hex")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_list_sends_groupbys_and_combined_orderbys(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        """search_alert.yaml:363-368 defines orderbys for the async path too."""
        route = respx.get(_ALERTS_URL).mock(
            return_value=httpx.Response(200, json={"result": [], "status": {"total": 0}})
        )
        paginated = aclient.alerts.list(group_by="alert_type", order_by="timestamp")
        _ = [alert async for alert in paginated]
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "alert_type"
        assert params["orderbys"] == "timestamp DESC"
        assert "sortby" not in params


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_contract_mock = respx.mock(assert_all_mocked=True, assert_all_called=False)


@pytest.mark.parametrize("model", [Alert, Event, Incident])
def test_the_epdlp_spelling_still_wins(model: type) -> None:
    """search_epdlp.yaml:88 is the one schema that spells it policy_name."""
    assert model.model_validate({"policy_name": "epdlp rule"}).policy_name == "epdlp rule"


@pytest.mark.parametrize("timeout", [0, -1, True, "180"])
@_contract_mock
def test_an_unusable_timeout_still_fails_before_http(
    contract_client: NetskopeClient, timeout: object
) -> None:
    with pytest.raises(ValidationError):
        contract_client.alerts.list_page(timeout=timeout)
    assert not _contract_mock.calls


@pytest.mark.parametrize("timeout", [0, -1, True, "180"])
@respx.mock
def test_an_unusable_timeout_fails_before_http(client: NetskopeClient, timeout: Any) -> None:
    with pytest.raises(ValidationError):
        client.alerts.list_page(timeout=timeout)
    assert not respx.calls


def test_a_bare_alert_row_still_decodes_object_categories() -> None:
    """dataexport.yaml:255-257 leaves the item type open entirely."""
    alert = Alert.model_validate({"_id": "a1", "other_categories": [{"id": 7}]})
    assert alert.other_categories == [{"id": 7}]
