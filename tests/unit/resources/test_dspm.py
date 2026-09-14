"""Tests for the DSPM resource with mocked HTTP.

Pins the wire shapes declared in ``production/endpoints/dspm/dspm_external.yaml``:
``list_resources`` reads the same routes as the typed surface (e.g.
``connected_datastores`` → ``GET /datastores/connected``, :6539) with
``filter``/``sortby``/``sortorder``/``offset``/``limit`` query params
(:6600-6637); ``analytics`` reads the two declared connected-datastore reports
(``sensitivityscoresdistribution`` :6508, ``privilegerisks`` :8039);
``scan_datastores`` loops over ``POST /datastores/connected/startscan``
(:6720); and ``connect_datastores`` is rejected client-side because no bulk
connect-by-id operation exists.  Resource names with no declared route are
rejected client-side (no HTTP) with :class:`ValidationError`.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.dspm import DspmResourceType, SortOrder
from netskope.resources.dspm.resource import AsyncDspmResource, DspmResource
from tests.unit.resources.conftest import sent_json

_BASE_URL = "https://t.goskope.com/api/v2/dspm"

# resource name -> the path dspm_external.yaml declares for it.
_ROUTED = {
    "connected_datastores": "/datastores/connected",
    "discovered_datastores": "/datastores/discovered",
    "archived_datastores": "/datastores/archived",
    "databases": "/datastores/connected/databases",
    "schemas": "/datastores/connected/schemas",
    "tables": "/datastores/connected/tables",
    "classification_columns": "/classificationmanagement/columns",
    "classification_files": "/classificationmanagement/files",
    "data_tags": "/classificationmanagement/datatags",
    "data_tag_categories": "/classificationmanagement/datatagcategories",
    "sensitive_data_types": "/classificationmanagement/sensitivedatatypes",
    "sensitive_data_type_categories": "/classificationmanagement/sensitivedatatypecategories",
    "sensitivity_levels": "/classificationmanagement/sensitivedatatypes/sensitivitylevels",
    "sidecar_pools": "/administration/sidecarpools",
    "infrastructure_connections": "/administration/infrastructureconnections",
    "infrastructure_platforms": "/administration/infrastructureconnections/platforms",
}
# Legacy names the SDK still accepts but the gateway never declared.
_UNROUTED = sorted({rt.value for rt in DspmResourceType} - set(_ROUTED))


def _dspm(client: NetskopeClient) -> DspmResource:
    return DspmResource(client._transport)


def _adspm(aclient: AsyncNetskopeClient) -> AsyncDspmResource:
    return AsyncDspmResource(aclient._transport)


class TestListResources:
    """Tests for DspmResource.list_resources."""

    @respx.mock
    def test_list_no_params(self, client: NetskopeClient) -> None:
        body = {"success": True, "data": {"total": 1, "results": [{"id": "db-1"}]}}
        route = respx.get(f"{_BASE_URL}/datastores/connected/databases").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = _dspm(client).list_resources("databases")

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_list_all_params(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE_URL}/datastores/connected").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {"results": []}})
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
        route = respx.get(f"{_BASE_URL}/classificationmanagement/columns").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {"results": []}})
        )
        _dspm(client).list_resources(
            DspmResourceType.CLASSIFICATION_COLUMNS,
            sort_order=SortOrder.ASC,
            sort_by="name",
        )
        request = route.calls.last.request
        assert request.url.path == "/api/v2/dspm/classificationmanagement/columns"
        assert dict(request.url.params) == {"sortby": "name", "sortorder": "asc"}

    @respx.mock
    @pytest.mark.parametrize(("resource_type", "path"), sorted(_ROUTED.items()))
    def test_every_routed_name_reaches_its_declared_path(
        self, client: NetskopeClient, resource_type: str, path: str
    ) -> None:
        route = respx.get(f"{_BASE_URL}{path}").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {"results": []}})
        )
        _dspm(client).list_resources(resource_type)
        assert route.calls.last.request.url.path == f"/api/v2/dspm{path}"

    @respx.mock
    @pytest.mark.parametrize("resource_type", _UNROUTED)
    def test_unrouted_names_raise_without_http(
        self, client: NetskopeClient, resource_type: str
    ) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="No verified public DSPM read contract"):
            _dspm(client).list_resources(resource_type)
        assert route.call_count == 0

    @respx.mock
    def test_invalid_resource_type_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="Invalid DSPM resource_type"):
            _dspm(client).list_resources("not_a_real_type")
        assert route.call_count == 0

    @respx.mock
    async def test_list_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"success": True, "data": {"results": [{"id": "t-1"}]}}
        route = respx.get(f"{_BASE_URL}/datastores/connected/tables").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = await _adspm(aclient).list_resources("tables", limit=5)

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert request.url.path == "/api/v2/dspm/datastores/connected/tables"
        assert dict(request.url.params) == {"limit": "5"}

    @respx.mock
    async def test_invalid_resource_type_async_no_http(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError):
            await _adspm(aclient).list_resources("bogus")
        assert route.call_count == 0


class TestAnalytics:
    """Tests for DspmResource.analytics — the two declared reports."""

    @respx.mock
    def test_sensitivity_score_distribution(self, client: NetskopeClient) -> None:
        body = {"success": True, "data": {"distribution": []}}
        route = respx.get(f"{_BASE_URL}/datastores/connected/sensitivityscoresdistribution").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = _dspm(client).analytics("sensitivity_score_distribution")

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_privilege_risks_takes_the_declared_query(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE_URL}/datastores/connected/privilegerisks").mock(
            return_value=httpx.Response(200, json={"success": True, "data": {"results": []}})
        )
        _dspm(client).analytics(
            "privilege_risks",
            filter_expr="cloud_provider_name eq 'AWS'",
            sort_by="name",
            sort_order="asc",
            limit=10,
            offset=5,
        )
        assert dict(route.calls.last.request.url.params) == {
            "filter": "cloud_provider_name eq 'AWS'",
            "sortby": "name",
            "sortorder": "asc",
            "limit": "10",
            "offset": "5",
        }

    @respx.mock
    def test_unknown_report_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="Unknown DSPM analytics report"):
            _dspm(client).analytics("summary")
        assert route.call_count == 0

    @respx.mock
    def test_distribution_rejects_query_parameters(self, client: NetskopeClient) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="takes no query parameters"):
            _dspm(client).analytics("sensitivity_score_distribution", limit=5)
        assert route.call_count == 0

    @respx.mock
    async def test_analytics_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"success": True, "data": {"results": []}}
        route = respx.get(f"{_BASE_URL}/datastores/connected/privilegerisks").mock(
            return_value=httpx.Response(200, json=body)
        )
        result = await _adspm(aclient).analytics("privilege_risks")

        assert result == body
        assert (
            route.calls.last.request.url.path == "/api/v2/dspm/datastores/connected/privilegerisks"
        )


class TestConnectDatastores:
    """The gateway has no bulk connect-by-id; the single create is a DataStoreRequest."""

    @respx.mock
    def test_bulk_connect_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="no bulk connect-by-id operation"):
            _dspm(client).connect_datastores(["ds-1", "ds-2"])
        assert route.call_count == 0

    @respx.mock
    def test_connect_datastore_posts_the_request_body(self, client: NetskopeClient) -> None:
        """``POST /datastores/connected`` takes a DataStoreRequest (dspm_external.yaml:6542)."""
        request_body = {
            "service_id": 3,
            "name": "prod-postgres",
            "endpoint": "prod.example.internal:5432",
            "authentication_method": "USERNAME_PASSWORD",
            "username": "scanner",
            "password": "secret",
        }
        route = respx.post(f"{_BASE_URL}/datastores/connected").mock(
            return_value=httpx.Response(201, json={"success": True})
        )
        result = _dspm(client).connect_datastore(request_body)

        assert result == {"success": True}
        assert sent_json(route) == request_body

    @respx.mock
    async def test_bulk_connect_async_raises(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="no bulk connect-by-id operation"):
            await _adspm(aclient).connect_datastores(["ds-9"])
        assert route.call_count == 0


class TestScanDatastores:
    """``POST /datastores/connected/startscan`` scans one datastore and answers 202."""

    @respx.mock
    def test_scan_posts_one_request_per_id(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/datastores/connected/startscan").mock(
            return_value=httpx.Response(202, json={"success": True})
        )
        assert _dspm(client).scan_datastores(["ds-1", "ds-2"]) is None

        assert route.call_count == 2
        bodies = [call.request.content for call in route.calls]
        assert bodies == [b'{"id":"ds-1"}', b'{"id":"ds-2"}']

    @respx.mock
    def test_scan_stops_at_the_first_failure(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/datastores/connected/startscan").mock(
            side_effect=[httpx.Response(202, json={}), httpx.Response(200, json={})]
        )
        with pytest.raises(ResponseValidationError, match="acknowledged with HTTP 202"):
            _dspm(client).scan_datastores(["ds-1", "ds-2", "ds-3"])
        assert route.call_count == 2

    @respx.mock
    async def test_scan_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE_URL}/datastores/connected/startscan").mock(
            return_value=httpx.Response(202, json={"success": True})
        )
        await _adspm(aclient).scan_datastores(["ds-1", "ds-2"])
        assert route.call_count == 2
