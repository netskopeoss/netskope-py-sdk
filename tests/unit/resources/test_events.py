"""Tests for client.events with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import NotFoundError, ValidationError
from netskope.models.events import NetworkEvent

_BASE = "https://t.goskope.com"
_APP_URL = f"{_BASE}/api/v2/events/datasearch/application"
_NETWORK_URL = f"{_BASE}/api/v2/events/datasearch/network"
_AUDIT_URL = f"{_BASE}/api/v2/events/data/audit"
_INFRA_URL = f"{_BASE}/api/v2/events/data/infrastructure"
_TRANSACTION_URL = f"{_BASE}/api/v2/events/metrics/transactionevents"

_EMPTY = {"result": [], "status": {"total": 0}}


class TestEventsResource:
    """Tests for client.events."""

    @respx.mock
    def test_list_application_events(self, client: NetskopeClient) -> None:
        respx.get(_APP_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "e1", "user": "alice@ex.com", "app": "Slack"}],
                    "status": {"total": 1},
                },
            )
        )
        events = list(client.events.list("application"))
        assert len(events) == 1
        assert events[0].app == "Slack"

    @respx.mock
    def test_list_network_events(self, client: NetskopeClient) -> None:
        respx.get(_NETWORK_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "result": [{"_id": "n1", "src_ip": "10.0.0.1", "dst_ip": "8.8.8.8"}],
                    "status": {"total": 1},
                },
            )
        )
        events = list(client.events.list("network"))
        assert len(events) == 1
        assert events[0].src_ip == "10.0.0.1"  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Endpoint routing
    # ------------------------------------------------------------------

    @respx.mock
    def test_audit_routes_to_data_audit_with_type_param(self, client: NetskopeClient) -> None:
        """Audit events use /events/data/audit and a ``type`` param, never ``query``."""
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("audit", audit_type="admin"))
        params = route.calls.last.request.url.params
        assert params["type"] == "admin"
        assert "query" not in params

    @respx.mock
    def test_audit_rejects_query_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.events.list("audit", query='user eq "a@ex.com"')
        assert len(respx.calls) == 0

    @respx.mock
    def test_infrastructure_routes_to_data_infrastructure(self, client: NetskopeClient) -> None:
        route = respx.get(_INFRA_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("infrastructure", query='status eq "down"'))
        assert route.called
        assert route.calls.last.request.url.path == "/api/v2/events/data/infrastructure"
        assert route.calls.last.request.url.params["query"] == 'status eq "down"'

    @respx.mock
    def test_transaction_routes_to_metrics_endpoint(self, client: NetskopeClient) -> None:
        route = respx.get(_TRANSACTION_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("transaction"))
        assert route.called
        assert route.calls.last.request.url.path == "/api/v2/events/metrics/transactionevents"

    @respx.mock
    def test_list_sends_groupbys_and_combined_sortby(self, client: NetskopeClient) -> None:
        """The datasearch API expects ``groupbys`` and ``sortby="field DESC|ASC"``."""
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(client.events.list("application", group_by="app", order_by="timestamp"))
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "app"
        assert "groupby" not in params
        assert params["sortby"] == "timestamp DESC"
        assert "sortorder" not in params

    @respx.mock
    def test_list_groupbys_joins_list_and_ascending_sort(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        list(
            client.events.list(
                "application",
                group_by=["app", "user"],
                order_by="timestamp",
                descending=False,
            )
        )
        params = route.calls.last.request.url.params
        assert params["groupbys"] == "app,user"
        assert params["sortby"] == "timestamp ASC"

    # ------------------------------------------------------------------
    # get()
    # ------------------------------------------------------------------

    @respx.mock
    def test_get_queries_by_id_with_limit_one(self, client: NetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "abc123", "user": "alice@ex.com"}]}
            )
        )
        event = client.events.get("abc123")
        assert event.id == "abc123"
        params = route.calls.last.request.url.params
        assert params["query"] == '_id eq "abc123"'
        assert params["limit"] == "1"

    @respx.mock
    def test_get_uses_type_specific_model(self, client: NetskopeClient) -> None:
        respx.get(_NETWORK_URL).mock(
            return_value=httpx.Response(
                200, json={"result": [{"_id": "beef01", "src_ip": "10.0.0.1"}]}
            )
        )
        event = client.events.get("beef01", event_type="network")
        assert isinstance(event, NetworkEvent)
        assert event.src_ip == "10.0.0.1"

    @respx.mock
    def test_get_rejects_non_hex_id_no_http(self, client: NetskopeClient) -> None:
        with pytest.raises(ValidationError):
            client.events.get("not-hex!")
        assert len(respx.calls) == 0

    @respx.mock
    def test_get_not_found(self, client: NetskopeClient) -> None:
        respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(NotFoundError):
            client.events.get("deadbeef")

    @respx.mock
    @pytest.mark.parametrize("event_type", ["audit", "transaction"])
    def test_get_rejects_unqueryable_types_no_http(
        self, client: NetskopeClient, event_type: str
    ) -> None:
        with pytest.raises(ValidationError):
            client.events.get("deadbeef", event_type=event_type)
        assert len(respx.calls) == 0


class TestAsyncEventsResource:
    """Tests for aclient.events."""

    @respx.mock
    async def test_get_queries_by_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_APP_URL).mock(
            return_value=httpx.Response(200, json={"result": [{"_id": "abc123"}]})
        )
        event = await aclient.events.get("abc123")
        assert event.id == "abc123"
        params = route.calls.last.request.url.params
        assert params["query"] == '_id eq "abc123"'
        assert params["limit"] == "1"

    @respx.mock
    async def test_get_rejects_non_hex_id_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            await aclient.events.get("zzz")
        assert len(respx.calls) == 0

    @respx.mock
    async def test_get_not_found(self, aclient: AsyncNetskopeClient) -> None:
        respx.get(_APP_URL).mock(return_value=httpx.Response(200, json={"result": []}))
        with pytest.raises(NotFoundError):
            await aclient.events.get("deadbeef")

    @respx.mock
    async def test_audit_routing_and_groupbys(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_AUDIT_URL).mock(return_value=httpx.Response(200, json=_EMPTY))
        paginated = aclient.events.list("audit", audit_type="user", group_by="user")
        _ = [event async for event in paginated]
        params = route.calls.last.request.url.params
        assert params["type"] == "user"
        assert params["groupbys"] == "user"

    @respx.mock
    async def test_audit_rejects_query_no_http(self, aclient: AsyncNetskopeClient) -> None:
        with pytest.raises(ValidationError):
            aclient.events.list("audit", query="x")
        assert len(respx.calls) == 0
