"""Tests for the DSPM resource with mocked HTTP.

Pins the wire shapes for the DSPM API: resources list via
``GET /api/v2/dspm/{resource_type}`` with ``filter``/``sortby``/``sortorder``/
``offset``/``limit`` query params, analytics via
``GET /api/v2/dspm/analytics/{metric_type}``, and connect/scan via
``POST`` with an ``{"ids": [...]}`` body.  Unknown resource types are rejected
client-side (no HTTP) with :class:`ValidationError`.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.dspm import DspmResourceType, SortOrder
from netskope.resources.dspm import AsyncDspmResource, DspmResource
from tests.unit.resources.conftest import sent_json

_BASE_URL = "https://t.goskope.com/api/v2/dspm"


def _dspm(client: NetskopeClient) -> DspmResource:
    return DspmResource(client._transport)


def _adspm(aclient: AsyncNetskopeClient) -> AsyncDspmResource:
    return AsyncDspmResource(aclient._transport)


class TestListResources:
    """Tests for DspmResource.list_resources."""

    @respx.mock
    def test_list_no_params(self, client: NetskopeClient) -> None:
        body = {"data": [{"id": "db-1"}], "status": "success"}
        route = respx.get(f"{_BASE_URL}/databases").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = _dspm(client).list_resources("databases")

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_list_all_params(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE_URL}/connected_datastores").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        _dspm(client).list_resources(
            "connected_datastores",
            filter_expr="name eq 'prod'",
            sort_by="name",
            sort_order="desc",
            limit=20,
            offset=40,
        )
        assert dict(route.calls.last.request.url.params) == {
            "filter": "name eq 'prod'",
            "sortby": "name",
            "sortorder": "desc",
            "limit": "20",
            "offset": "40",
        }

    @respx.mock
    def test_list_accepts_enum_members(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE_URL}/policy_violations").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        _dspm(client).list_resources(
            DspmResourceType.POLICY_VIOLATIONS,
            sort_order=SortOrder.ASC,
            sort_by="created_at",
        )
        request = route.calls.last.request
        assert request.url.path == "/api/v2/dspm/policy_violations"
        assert dict(request.url.params) == {"sortby": "created_at", "sortorder": "asc"}

    @respx.mock
    @pytest.mark.parametrize("resource_type", [rt.value for rt in DspmResourceType])
    def test_path_interpolation_all_types(self, client: NetskopeClient, resource_type: str) -> None:
        route = respx.get(f"{_BASE_URL}/{resource_type}").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        _dspm(client).list_resources(resource_type)
        assert route.calls.last.request.url.path == f"/api/v2/dspm/{resource_type}"

    @respx.mock
    def test_invalid_resource_type_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="Invalid DSPM resource_type"):
            _dspm(client).list_resources("not_a_real_type")
        assert route.call_count == 0

    @respx.mock
    async def test_list_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": [{"id": "t-1"}]}
        route = respx.get(f"{_BASE_URL}/tables").mock(return_value=httpx.Response(200, json=body))
        result = await _adspm(aclient).list_resources("tables", limit=5)

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.url.path == "/api/v2/dspm/tables"
        assert dict(request.url.params) == {"limit": "5"}

    @respx.mock
    async def test_invalid_resource_type_async_no_http(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            await _adspm(aclient).list_resources("bogus")
        assert route.call_count == 0


class TestAnalytics:
    """Tests for DspmResource.analytics."""

    @respx.mock
    def test_analytics(self, client: NetskopeClient) -> None:
        body = {"data": {"total": 42}}
        route = respx.get(f"{_BASE_URL}/analytics/summary").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = _dspm(client).analytics("summary")

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.url.path == "/api/v2/dspm/analytics/summary"

    @respx.mock
    def test_analytics_metric_is_path_encoded(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE_URL}/analytics/risk%2Fscore").mock(
            return_value=httpx.Response(200, json={})
        )
        _dspm(client).analytics("risk/score")
        # quote_id encodes '/' so it cannot alter the request path.
        assert route.calls.last.request.url.raw_path.endswith(b"/analytics/risk%2Fscore")

    @respx.mock
    async def test_analytics_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": {"score": 1}}
        route = respx.get(f"{_BASE_URL}/analytics/risk_score").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = await _adspm(aclient).analytics("risk_score")

        assert result == body
        assert route.calls.last.request.url.path == "/api/v2/dspm/analytics/risk_score"


class TestConnectDatastores:
    """Tests for DspmResource.connect_datastores."""

    @respx.mock
    def test_connect(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/connected_datastores").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = _dspm(client).connect_datastores(["ds-1", "ds-2"])

        assert result == {"status": "success"}
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"ids": ["ds-1", "ds-2"]}

    @respx.mock
    async def test_connect_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/connected_datastores").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await _adspm(aclient).connect_datastores(["ds-9"])
        assert sent_json(route) == {"ids": ["ds-9"]}


class TestScanDatastores:
    """Tests for DspmResource.scan_datastores."""

    @respx.mock
    def test_scan(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/scans").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        result = _dspm(client).scan_datastores(["ds-1"])

        assert result == {"status": "success"}
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"ids": ["ds-1"]}

    @respx.mock
    async def test_scan_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/scans").mock(
            return_value=httpx.Response(200, json={"status": "success"})
        )
        await _adspm(aclient).scan_datastores(["ds-1", "ds-2"])
        assert sent_json(route) == {"ids": ["ds-1", "ds-2"]}
