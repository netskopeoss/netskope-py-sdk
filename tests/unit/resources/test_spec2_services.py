"""SPEC2 conformance checks for the DEM/ADEM, SPM, DSPM, ATP, RBI, IPS, CCI,
NSIQ and notifications surfaces.

Every assertion cites the production contract file and line it comes from, and
every request is mocked: these tests never touch a tenant.  Response fixtures
use the contract's own example values where the operation supplies one.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, ClassVar

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.atp import AtpFileSubmission, AtpSubmissionReport, AtpUrlSubmission
from netskope.models.cci import CciTagCreate, CciTagPatch
from netskope.models.dem import AdemGraphEdge, AdemNetworkGraph, DemQueryRequest
from netskope.models.notifications import NotificationTemplateWrite
from netskope.models.nsiq import RecategorizationReceipt, RecategorizationUrl
from netskope.models.rbi import RbiTemplateSettings, RbiToggle
from netskope.models.spm import SpmInstanceScore, SpmTrendSample

_TENANT = "example.goskope.coken"
_BASE = f"https://{_TENANT}"


@pytest.fixture
def client() -> Iterator[NetskopeClient]:
    """A sync client against a synthetic tenant that resolves to no real host."""
    with NetskopeClient(
        tenant=_TENANT, api_token="synthetic-token", allow_custom_tenant=True, max_retries=0
    ) as c:
        yield c


@pytest.fixture
async def aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """The async twin of :func:`client`."""
    async with AsyncNetskopeClient(
        tenant=_TENANT, api_token="synthetic-token", allow_custom_tenant=True, max_retries=0
    ) as c:
        yield c


def _mock() -> respx.Router:
    """A router that fails the test if the SDK sends an unmocked request.

    ``assert_all_called`` is off because several checks assert that a route is
    *never* reached; each such test asserts ``call_count`` itself.
    """
    return respx.mock(assert_all_mocked=True, assert_all_called=False, base_url=_BASE)


# --- SPEC2-SPM-1: sparse recent-changes samples ----------------------------


class TestSpmRecentChangesAreSparse:
    _BODY: ClassVar[dict[str, Any]] = {
        "trends": {
            "samples": [{"posture_confidence_index": 70, "posture_scores": [{"id": "M365"}]}],
            "by_trajectory": {"up": ["M365"]},
        }
    }

    def test_models_require_nothing(self) -> None:
        """``RecentChangesResponse`` declares no ``required`` list at any level:
        the samples items (spm/apps.yaml:656-690) and their ``posture_scores``
        items (:678-690) are all optional."""
        assert SpmTrendSample.model_validate({"posture_confidence_index": 70}).timestamp is None
        assert SpmInstanceScore.model_validate({"id": "M365"}).posture_score is None
        assert SpmInstanceScore.model_validate({"posture_score": 80}).id is None

    def test_sync_parses_a_sample_without_timestamp_or_score(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            mock.post("/api/v2/spm/apps/recentchanges/getstats").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            changes = client.spm.with_response.recent_changes(
                start=1758127874, end=1759127874
            ).parse()
        assert changes.trends is not None
        sample = changes.trends.samples[0]
        assert sample.timestamp is None and sample.posture_confidence_index == 70
        assert sample.posture_scores[0].id == "M365"

    async def test_async_parses_the_same_body(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            mock.post("/api/v2/spm/apps/recentchanges/getstats").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            response = await aclient.spm.with_response.recent_changes(
                start=1758127874, end=1759127874
            )
        changes = response.parse()
        assert changes.trends is not None and changes.trends.samples[0].timestamp is None


# --- SPEC2-NSIQ-1: sparse recategorization receipt -------------------------


class TestRecategorizationReceiptIsSparse:
    def test_models_require_nothing(self) -> None:
        """``SubmissionDetail`` (nsiq/url_recategorization.yaml:150-158) and
        ``RecatUrlId`` (:93-107) declare no ``required`` list."""
        assert RecategorizationReceipt.model_validate({}).task_id is None
        assert RecategorizationUrl.model_validate({"url": "http://x.example"}).id is None

    def test_sync_parses_a_receipt_without_task_id(self, client: NetskopeClient) -> None:
        from netskope.models.nsiq import RecategorizationRequest, UrlRecategorization

        request = RecategorizationRequest(
            recat_requests=[UrlRecategorization(url="http://x.example", suggested_categories=["A"])]
        )
        with _mock() as mock:
            mock.post("/api/v2/nsiq/url/recategorizations").mock(
                return_value=httpx.Response(
                    201, json={"status": "success", "data": {"urls": [{"url": "http://x.example"}]}}
                )
            )
            receipt = client.nsiq.with_response.recategorize(request).parse()
        assert receipt.task_id is None and receipt.urls[0].url == "http://x.example"


# --- SPEC2-ATP-1: sparse ATP acknowledgements ------------------------------


class TestAtpAcknowledgementsAreSparse:
    def test_models_require_nothing(self) -> None:
        """``TssScanAPIResponse`` (atp/atpsvc.yaml:16-31), ``ScanInProgress``
        (atp/urlscan.yaml:43-55) and ``GetReportResponse``
        (atp/tpaassvc.yaml:64-70) declare no ``required`` list."""
        assert AtpFileSubmission.model_validate({"status": "Ok", "md5": "0" * 32}).job_id is None
        assert (
            AtpUrlSubmission.model_validate({"status": "Ok", "message": "queued"}).submission_id
            is None
        )
        assert AtpSubmissionReport.model_validate({"processtree": "[]"}).report == {}

    def test_submission_report_without_report_parses(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            mock.get("/api/v2/atp/tpaas/submission/s1/reports").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "processtree": '[{"track": true, "pid": 1140, '
                        '"process_name": "WINWORD.EXE"}]'
                    },
                )
            )
            report = client.atp.with_response.get_submission_report("s1").parse()
        assert report.report == {} and report.process_tree is not None


# --- SPEC2-RBI-2: watermark carries its own optional enabled ---------------


class TestRbiWatermarkIsOptional:
    def test_watermark_without_enabled_decodes(self) -> None:
        """``watermark.enabled`` is in no ``required`` list and the contract
        notes migrated tenants may not carry it (rbi/templates.yaml:1654-1661);
        ``TemplateData`` also leaves ``watermark`` itself out of its required
        set (:1662-1678)."""
        settings = RbiTemplateSettings.model_validate({"name": "t", "watermark": {}})
        assert settings.watermark is not None and settings.watermark.enabled is None

    def test_the_other_toggles_still_require_enabled(self) -> None:
        """Every other ``$Enabled`` toggle requires ``enabled``."""
        with pytest.raises(Exception, match="enabled"):
            RbiToggle.model_validate({})


# --- SPEC2-RBI-1: GET /templates query enumerations ------------------------


class TestRbiTemplateQueryEnums:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"sort_by": "nope"}, "sort_by must be one of"),
            ({"sort_order": "sideways"}, "sort_order must be one of"),
            ({"status": ["bogus"]}, "Invalid status value"),
            ({"fields": ["not_a_field"]}, "Invalid fields value"),
            ({"status": []}, "at least one template status"),
        ],
    )
    def test_unenumerated_values_are_rejected(
        self, client: NetskopeClient, kwargs: dict[str, Any], message: str
    ) -> None:
        """``sortby`` (rbi/templates.yaml:181-194), ``sortorder`` (:195-206),
        ``status`` (:207-229, ``minItems: 1``) and ``fields`` (:230-257) are all
        enumerated."""
        with _mock() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match=message):
                client.rbi.list_templates(**kwargs)
            assert route.call_count == 0

    def test_declared_values_are_comma_joined(self, client: NetskopeClient) -> None:
        """``status`` and ``fields`` are ``style: form, explode: false``
        (rbi/templates.yaml:218-219, :237-238)."""
        with _mock() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={"templates": []})
            )
            client.rbi.list_templates(
                sort_by="template_name",
                sort_order="desc",
                status=["applied", "pending-update"],
                fields=["name", "watermark"],
            )
        assert dict(route.calls.last.request.url.params) == {
            "sortby": "template_name",
            "sortorder": "desc",
            "status": "applied,pending-update",
            "fields": "name,watermark",
        }

    async def test_async_rejects_the_same_values(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            route = mock.get("/api/v2/rbi/templates").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match="sort_by must be one of"):
                await aclient.rbi.list_templates(sort_by="nope")
            assert route.call_count == 0


# --- SPEC2-IPS-1: limit is bounded to [1, 100] on every path ---------------


class TestIpsLimitBounds:
    _OK: ClassVar[dict[str, Any]] = {"status": "Success", "data": []}

    @pytest.mark.parametrize("limit", [0, 101, 5000])
    def test_out_of_range_limits_are_rejected(self, client: NetskopeClient, limit: int) -> None:
        """``GET /signaturereferencelist`` (ips/ms-ips.yaml:583-592),
        ``POST /getsignaturelist`` (:721-727) and ``GET /signatureoverrides``
        (:1177-1186) declare ``limit`` as ``minimum: 1, maximum: 100``."""
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            for call in (
                lambda: client.ips.list_signatures(limit=limit),
                lambda: client.ips.with_response.list_signatures(limit=limit),
                lambda: client.ips.search_signatures(limit=limit),
                lambda: client.ips.list_signature_overrides(limit=limit),
            ):
                with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                    call()
            assert route.call_count == 0

    @pytest.mark.parametrize("limit", [1, 100])
    def test_boundary_limits_are_sent(self, client: NetskopeClient, limit: int) -> None:
        with _mock() as mock:
            references = mock.get("/api/v2/ips/signaturereferencelist").mock(
                return_value=httpx.Response(200, json={"status": "Success", "data": []})
            )
            search = mock.post("/api/v2/ips/getsignaturelist").mock(
                return_value=httpx.Response(200, json=self._OK)
            )
            client.ips.list_signatures(limit=limit)
            client.ips.with_response.list_signatures(limit=limit).parse()
            client.ips.search_signatures(limit=limit)
        assert references.calls.last.request.url.params["limit"] == str(limit)
        assert json.loads(search.calls.last.request.content)["limit"] == limit

    async def test_async_paths_apply_the_same_bound(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await aclient.ips.list_signatures(limit=5000)
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await aclient.ips.with_response.list_signatures(limit=0)
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await aclient.ips.search_signatures(limit=101)
            assert route.call_count == 0


# --- SPEC2-NSIQ-2: recategorization list bounds and enumerations -----------


class TestRecategorizationListInputs:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"limit": 11}, "limit must be an integer between 1 and 10"),
            ({"limit": 0}, "limit must be an integer between 1 and 10"),
            ({"offset": -1}, "offset must be a nonnegative integer"),
            ({"status": "bogus"}, "status must be one of"),
            ({"sort_by": "nope"}, "sort_by must be one of"),
            ({"sort_order": "sideways"}, "sort_order must be one of"),
        ],
    )
    def test_invalid_inputs_are_rejected(
        self, client: NetskopeClient, kwargs: dict[str, Any], message: str
    ) -> None:
        """``GET /url/recategorizations`` declares ``limit``
        ``minimum: 1, maximum: 10`` (nsiq/url_recategorization.yaml:339-347),
        ``offset`` ``minimum: 0`` (:329-338), and enumerates ``status``
        (:318-328), ``sortby`` (:348-359) and ``sortorder`` (:360-369)."""
        with _mock() as mock:
            route = mock.get("/api/v2/nsiq/url/recategorizations").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match=message):
                client.nsiq.list_recategorizations(**kwargs)
            assert route.call_count == 0

    @pytest.mark.parametrize("limit", [1, 10])
    def test_boundary_and_enumerated_values_are_sent(
        self, client: NetskopeClient, limit: int
    ) -> None:
        with _mock() as mock:
            route = mock.get("/api/v2/nsiq/url/recategorizations").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            client.nsiq.list_recategorizations(
                limit=limit, offset=0, status="completed", sort_by="start_time", sort_order="desc"
            )
        assert dict(route.calls.last.request.url.params) == {
            "limit": str(limit),
            "offset": "0",
            "status": "completed",
            "sortby": "start_time",
            "sortorder": "desc",
        }

    async def test_async_rejects_the_same_inputs(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            route = mock.get("/api/v2/nsiq/url/recategorizations").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.raises(ValidationError, match="limit must be an integer between 1 and 10"):
                await aclient.nsiq.list_recategorizations(limit=500)
            assert route.call_count == 0


# --- SPEC2-CCI-1 / CCI-2: one selector, and integer application ids --------


class TestCciApplicationQueryAndTagIds:
    def test_legacy_and_typed_paths_agree_on_one_selector(self, client: NetskopeClient) -> None:
        """``GET /cci/app``: "All the query parameters are mutually exclusive
        except limit & offset" (services/cci.yaml:2889)."""
        from netskope.models.cci import CciAppQuery

        with _mock() as mock:
            route = mock.get("/api/v2/services/cci/app").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            with pytest.raises(ValidationError, match="exactly one CCI selector"):
                client.cci.lookup_app("Dropbox", ccl="high")
            # The typed surface already rejected the pair at construction.
            with pytest.raises(Exception, match="exactly one CCI selector"):
                CciAppQuery(apps=["Dropbox"], ccl="high")
            client.cci.with_response.list_page(CciAppQuery(apps=["Dropbox"])).parse()
            assert route.call_count == 1

    def test_tag_writes_accept_the_integer_ids_the_example_uses(
        self, client: NetskopeClient
    ) -> None:
        """``appTagExample``; the example the ``POST /cci/tags`` body points at
        ; writes ``ids`` as integers (services/cci.yaml:48-57)."""
        assert CciTagCreate(tag="ccl_high", ids=[1, 2]).ids == [1, 2]
        assert CciTagPatch(action="append", ids=[1, 2]).ids == [1, 2]
        with _mock() as mock:
            create = mock.post("/api/v2/services/cci/tags").mock(
                return_value=httpx.Response(200, json={"status": "Success"})
            )
            patch = mock.patch("/api/v2/services/cci/tags/ccl_high").mock(
                return_value=httpx.Response(200, json={"status": "Success"})
            )
            client.cci.tags.with_response.create_request(CciTagCreate(tag="ccl_high", ids=[1, 2]))
            client.cci.tags.with_response.update_request(
                "ccl_high", CciTagPatch(action="append", ids=[1, 2])
            )
        assert json.loads(create.calls.last.request.content)["ids"] == [1, 2]
        assert json.loads(patch.calls.last.request.content)["ids"] == [1, 2]

    async def test_async_tag_create_sends_integer_ids(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            create = mock.post("/api/v2/services/cci/tags").mock(
                return_value=httpx.Response(200, json={"status": "Success"})
            )
            await aclient.cci.tags.with_response.create_request(
                CciTagCreate(tag="ccl_high", ids=[1, 2])
            )
        assert json.loads(create.calls.last.request.content)["ids"] == [1, 2]


# --- SPEC2-DEM-2: alert entities are ImpactEntity rows ---------------------


class TestAlertEntitiesDecode:
    _BODY: ClassVar[dict[str, Any]] = {
        "entities": [
            {
                "name": "pop-sjc1",
                "impactType": "latency",
                "metricType": "popLatency_p95",
                "metricValues": [{"timestamp": 1700000000, "value": 42}],
                "pop": "SJC1",
                "publisher": "pub-1",
                "resource": "res-1",
                "service": "svc-1",
                "site": "site-1",
                "sourceIP": "203.0.113.9",
                "status": "triggered",
            }
        ],
        "limit": 5,
        "offset": 0,
        "totalCount": 1,
    }

    def test_sync_maps_every_declared_property(self, client: NetskopeClient) -> None:
        """``GET /alerts/{id}/entities`` returns ``AlertEntityDetail``
        (dem_alert.yaml:87-105) whose items are ``ImpactEntity`` (:342-381),
        with ``metricValues`` items ``MetricValue`` (:382-391)."""
        with _mock() as mock:
            mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            rows = client.dem.alerts.with_response.entities("a1").parse()
        entity = rows[0]
        assert entity.name == "pop-sjc1"
        assert entity.impact_type == "latency" and entity.metric_type == "popLatency_p95"
        assert entity.metric_values[0].timestamp == 1700000000
        assert entity.metric_values[0].value == 42
        assert entity.source_ip == "203.0.113.9" and entity.status == "triggered"
        assert (entity.pop, entity.publisher, entity.resource) == ("SJC1", "pub-1", "res-1")
        assert (entity.service, entity.site) == ("svc-1", "site-1")
        assert not entity.model_extra

    async def test_async_decodes_the_same_rows(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            response = await aclient.dem.alerts.with_response.entities("a1")
        assert response.parse()[0].pop == "SJC1"

    def test_sortorder_is_enumerated_on_both_surfaces(self, client: NetskopeClient) -> None:
        """``sortorder`` on ``/alerts/{id}/entities`` enumerates asc|desc
        (dem_alert.yaml:1813-1822)."""
        with _mock() as mock:
            route = mock.get("/api/v2/dem/alerts/a1/entities").mock(
                return_value=httpx.Response(200, json={"entities": []})
            )
            with pytest.raises(ValidationError, match="sort_order must be one of"):
                client.dem.alerts.entities("a1", sort_order="sideways")
            with pytest.raises(ValidationError, match="sort_order must be one of"):
                client.dem.alerts.with_response.entities("a1", sort_order="sideways")
            assert route.call_count == 0


# --- SPEC2-ADEM-1: sparse network graphs ----------------------------------


class TestNetworkGraphsAreSparse:
    def test_models_follow_the_looser_of_the_two_operations(self) -> None:
        """``TracerData`` (adem_backend_api.yaml:1767-1782) requires neither
        ``nodes`` nor ``edges``, and ``NetworkEdge`` (:1315-1331) requires
        neither ``source`` nor ``destination``; ``NetworkNode`` (:1277-1314)
        requires nothing at all."""
        graph = AdemNetworkGraph.model_validate({"nodes": [{"id": "1", "hopType": "device"}]})
        assert graph.edges == [] and graph.nodes[0].hop_type == "device"
        edge = AdemGraphEdge.model_validate({"noOfSessions": 3, "avgLatency": 11})
        assert edge.source is None and edge.destination is None and edge.sessions == 3

    def test_traceroute_parses_a_nodes_only_body(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            mock.post("/api/v2/adem/users/device/gettraceroute").mock(
                return_value=httpx.Response(
                    200, json={"nodes": [{"id": "1", "hopType": "device"}], "isComplete": True}
                )
            )
            graph = client.dem.users.with_response.traceroute(
                "u@example.com", "device-1", start_time=1700000000, end_time=1700003600
            ).parse()
        assert graph.complete is True and graph.edges == []

    async def test_async_network_paths_parse_edges_without_endpoints(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with _mock() as mock:
            mock.post("/api/v2/adem/users/npa/getnetworkpaths").mock(
                return_value=httpx.Response(
                    200, json={"nodes": [], "edges": [{"noOfSessions": 3, "avgLatency": 11}]}
                )
            )
            response = await aclient.dem.users.with_response.npa_network_paths(
                "u@example.com", "device-1", "host-1", start_time=1700000000, end_time=1700003600
            )
        assert response.parse().edges[0].sessions == 3


# --- SPEC2-DEM-3 / DEM-5: query windows and paging bounds -----------------


class TestDemQueryBounds:
    _WINDOW: ClassVar[dict[str, int]] = {
        "start_time": 1700000000,
        "end_time": 1700000000 + 72 * 3600,
    }

    async def test_getentities_window_is_not_capped(self, aclient: AsyncNetskopeClient) -> None:
        """``GetEntitiesQueryInput`` types ``starttime``/``endtime`` as plain
        integers with no bound (dem-workbench-query.yaml:296-366) and
        ``/query/getentities`` (:1208) documents no range cap; only
        ``/query/getdataset`` does (:918)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getentities").mock(
                return_value=httpx.Response(200, json={"users": [], "totalUsersCount": 0})
            )
            await aclient.dem.query.get_entities(**self._WINDOW)
            response = await aclient.dem.query.with_response.get_entities(**self._WINDOW)
        response.parse()
        assert route.call_count == 2

    def test_getdataset_keeps_the_documented_two_day_cap(self, client: NetskopeClient) -> None:
        """``/query/getdataset`` states "Maximum allowed range: 2 days"
        (dem-workbench-query.yaml:918, in the operation
        description that starts at :893)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getdataset").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            with pytest.raises(ValidationError, match="must not exceed 48 hours"):
                client.dem.query.with_response.get_dataset(
                    "http_all", ["user"], begin=0, end=49 * 3600 * 1000
                )
            assert route.call_count == 0

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"limit": 10000}, "limit must be an integer between 0 and 9999"),
            ({"offset": 100000}, "offset must be an integer between 0 and 99999"),
        ],
    )
    def test_legacy_getstates_applies_the_state_query_bounds(
        self, client: NetskopeClient, kwargs: dict[str, int], message: str
    ) -> None:
        """``StateQueryInput.limit`` is ``exclusiveMaximum: 10000`` and
        ``.offset`` ``exclusiveMaximum: 100000``
        (dem-workbench-query.yaml:534-548)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getstates").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            with pytest.raises(ValidationError, match=message):
                client.dem.query.get_states("client_status", ["user"], **kwargs)
            assert route.call_count == 0

    def test_legacy_getstates_sends_the_boundary_values(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getstates").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            client.dem.query.get_states("client_status", ["user"], limit=9999, offset=99999)
        body = json.loads(route.calls.last.request.content)
        assert body["limit"] == 9999 and body["offset"] == 99999

    async def test_async_legacy_getdata_rejects_an_out_of_range_limit(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getdata").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            message = "limit must be an integer between 0 and 9999"
            with pytest.raises(ValidationError, match=message):
                await aclient.dem.query.get_data("http", ["x"], begin=1, end=2, limit=123456)
            assert route.call_count == 0


# --- SPEC2-DEM-7: the declared window rules -------------------------------


class TestDemQueryWindowRules:
    _BOUND: ClassVar[dict[str, str]] = {"absolute": "2024-01-01T00:00:00Z"}

    def test_equal_and_mixed_bounds_are_accepted(self) -> None:
        """``QueryInput`` types ``begin`` and ``end`` as independent
        ``anyOf[AbsoluteDate, RelativeDate, null]`` values
        (dem-workbench-query.yaml:422-433): no ordering rule, and no rule that
        both use the same mode."""
        equal = DemQueryRequest.model_validate(
            {"from": "http", "select": ["u"], "begin": self._BOUND, "end": self._BOUND}
        )
        assert equal.begin == equal.end
        mixed = DemQueryRequest.model_validate(
            {
                "from": "http",
                "select": ["u"],
                "begin": {"relative": "2024-01-01T00:00:00Z"},
                "end": self._BOUND,
            }
        )
        assert mixed.begin == {"relative": "2024-01-01T00:00:00Z"}

    def test_an_inverted_same_mode_window_is_still_rejected(self) -> None:
        with pytest.raises(Exception, match="end must not precede begin"):
            DemQueryRequest.model_validate(
                {
                    "from": "http",
                    "select": ["u"],
                    "begin": {"absolute": "2024-01-02T00:00:00Z"},
                    "end": self._BOUND,
                }
            )

    def test_relative_bounds_are_timestamps(self) -> None:
        """``RelativeDate.relative`` is a ``format: date-time`` string
        (dem-workbench-query.yaml:498-507), not an offset expression."""
        with pytest.raises(Exception, match="RFC 3339"):
            DemQueryRequest.model_validate(
                {"from": "http", "select": ["u"], "begin": {"relative": "-24h"}}
            )

    def test_the_typed_surface_sends_an_equal_window(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            route = mock.post("/api/v2/dem/query/getdata").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            client.dem.query.with_response.get_data(
                "rum_steered", ["country"], begin=1704067200000, end=1704067200000
            ).parse()
        body = json.loads(route.calls.last.request.content)
        assert body["begin"] == body["end"] == {"absolute": "2024-01-01T00:00:00Z"}


# --- SPEC2-DEM-4: probe and app list paging bounds ------------------------


class TestDemListPagingBounds:
    @pytest.mark.parametrize("limit", [0, 1001])
    def test_probe_lists_reject_out_of_range_limits(
        self, client: NetskopeClient, limit: int
    ) -> None:
        """``GET /appprobes`` (demconfig.yaml:625-631) and ``GET /networkprobes``
        (:1560-1566) declare ``limit`` as ``minimum: 1, maximum: 1000``."""
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            for call in (
                lambda: client.dem.probes.list(limit=limit),
                lambda: client.dem.probes.with_response.list(limit=limit),
                lambda: client.dem.network_probes.list(limit=limit),
                lambda: client.dem.network_probes.with_response.list(limit=limit),
            ):
                with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                    call()
            assert route.call_count == 0

    @pytest.mark.parametrize("limit", [1, 1000])
    def test_probe_lists_send_the_boundary_limits(self, client: NetskopeClient, limit: int) -> None:
        with _mock() as mock:
            route = mock.get("/api/v2/dem/appprobes").mock(
                return_value=httpx.Response(200, json={"totalCount": 0, "probes": []})
            )
            client.dem.probes.list(limit=limit, offset=0)
            client.dem.probes.with_response.list(limit=limit, offset=0).parse()
        assert dict(route.calls.last.request.url.params) == {"limit": str(limit), "offset": "0"}

    def test_app_list_requires_at_least_one_row(self, client: NetskopeClient) -> None:
        """``GET /apps`` declares ``limit`` ``minimum: 1`` with no maximum
        (demconfig.yaml:110-116)."""
        with _mock() as mock:
            route = mock.get("/api/v2/dem/apps").mock(
                return_value=httpx.Response(200, json={"apps": []})
            )
            with pytest.raises(ValidationError, match="limit must be an integer 1 or more"):
                client.dem.apps.list(limit=0)
            with pytest.raises(ValidationError, match="limit must be an integer 1 or more"):
                client.dem.apps.with_response.list(limit=0)
            client.dem.apps.list(limit=5000)
            assert route.calls.last.request.url.params["limit"] == "5000"

    async def test_async_probe_lists_apply_the_same_bounds(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await aclient.dem.probes.list(limit=5000)
            with pytest.raises(ValidationError, match="limit must be an integer between 1"):
                await aclient.dem.network_probes.with_response.list(limit=0)
            with pytest.raises(ValidationError, match="offset must be an integer 0 or more"):
                await aclient.dem.probes.list(offset=-1)
            assert route.call_count == 0


# --- SPEC2-DEM-6: DEM request enumerations --------------------------------


class TestDemRequestEnums:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"category": "Nope"}, "category must be one of"),
            ({"type": "Nope"}, "type must be one of"),
            ({"severity": "apocalyptic"}, "severity must be one of"),
        ],
    )
    def test_alert_rule_filters_are_enumerated(
        self, client: NetskopeClient, kwargs: dict[str, str], message: str
    ) -> None:
        """``GET /alert/rules`` filters by ``AlertCategory`` (dem_alert.yaml:79-86),
        ``AlertType`` (:304-314) and ``AlertSeverity`` (:288-296)."""
        with _mock() as mock:
            route = mock.get("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"rules": []})
            )
            with pytest.raises(ValidationError, match=message):
                client.dem.alert_rules.list(**kwargs)
            assert route.call_count == 0

    def test_declared_alert_rule_filters_are_sent(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            route = mock.get("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"rules": []})
            )
            client.dem.alert_rules.list(
                category="User Experience", type="Experience Score", severity="high", enabled=True
            )
        assert dict(route.calls.last.request.url.params) == {
            "category": "User Experience",
            "type": "Experience Score",
            "severity": "high",
            "enabled": "true",
        }

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"alert_category": ["Nope"]}, "Invalid alert_category value"),
            ({"alert_type": ["Nope"]}, "Invalid alert_type value"),
            ({"severity": ["apocalyptic"]}, "Invalid severity value"),
        ],
    )
    def test_getalerts_lists_are_enumerated(
        self, client: NetskopeClient, kwargs: dict[str, list[str]], message: str
    ) -> None:
        """``AlertQuery`` types ``alertCategory``, ``alertType`` and ``severity``
        as arrays of those same enumerations (dem_alert.yaml:138-173)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/alerts/getalerts").mock(
                return_value=httpx.Response(200, json={"alerts": []})
            )
            with pytest.raises(ValidationError, match=message):
                client.dem.alerts.search(**kwargs)
            with pytest.raises(ValidationError, match=message):
                client.dem.alerts.with_response.search(**kwargs)
            assert route.call_count == 0

    def test_alert_rule_create_enumerations(self, client: NetskopeClient) -> None:
        """``PostAlertRuleRequest`` refers to the same three enumerations
        (dem_alert.yaml:441-462)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/alert/rules").mock(
                return_value=httpx.Response(200, json={"id": "1"})
            )
            with pytest.raises(ValidationError, match="severity must be one of"):
                client.dem.alert_rules.create(
                    "r", "userDemScore", 80.0, severity="apocalyptic", criteria={"condition": {}}
                )
            with pytest.raises(ValidationError, match="category must be one of"):
                client.dem.alert_rules.create(
                    "r", "userDemScore", 80.0, category="Nope", criteria={"condition": {}}
                )
            assert route.call_count == 0

    def test_probe_create_enumerations(self, client: NetskopeClient) -> None:
        """``AppProbeUpdateCreateCommon`` enumerates ``os`` (windows|mac) and
        ``deviceClassification`` (managed|unmanaged|not configured)
        (demconfig.yaml:2690-2704)."""
        with _mock() as mock:
            route = mock.post("/api/v2/dem/appprobes").mock(
                return_value=httpx.Response(200, json={"id": 1})
            )
            with pytest.raises(ValidationError, match="Invalid os value"):
                client.dem.probes.create(
                    "p",
                    app_name="Slack",
                    frequency=5,
                    entity={"user": ["u"]},
                    os=["plan9"],
                    device_classification=["managed"],
                )
            with pytest.raises(ValidationError, match="Invalid device_classification value"):
                client.dem.probes.create(
                    "p",
                    app_name="Slack",
                    frequency=5,
                    entity={"user": ["u"]},
                    os=["windows"],
                    device_classification=["unknown"],
                )
            assert route.call_count == 0

    async def test_async_surfaces_apply_the_same_enumerations(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="category must be one of"):
                await aclient.dem.alert_rules.list(category="Nope")
            with pytest.raises(ValidationError, match="Invalid severity value"):
                await aclient.dem.alerts.search(severity=["apocalyptic"])
            with pytest.raises(ValidationError, match="monitoring must be one of"):
                await aclient.dem.query.get_entities(
                    start_time=1700000000, end_time=1700003600, monitoring="telepathy"
                )
            assert route.call_count == 0


# --- SPEC2-NOTIF-1: the legacy template writes apply the declared rules ----


class TestNotificationTemplateRules:
    _TEMPLATE: ClassVar[dict[str, str]] = {"id": "42", "name": "Custom Block Page"}

    def test_create_applies_lengths_and_button_rules(self, client: NetskopeClient) -> None:
        """``NotificationsCreateRequest`` caps ``title`` at 60 and each button
        label at 14 characters, and its property descriptions make
        ``ackButtonText`` required for ``block`` and disallowed for
        ``useralert`` (user-notifications-templates.yaml:10-91)."""
        with _mock() as mock:
            route = mock.post("/api/v2/notifications/user/templates").mock(
                return_value=httpx.Response(201, json=self._TEMPLATE)
            )
            with pytest.raises(ValidationError, match="title"):
                client.notifications.create_template(
                    "n", title="T" * 80, message="m", ack_button_text="OK"
                )
            with pytest.raises(ValidationError, match="ackButtonText"):
                client.notifications.create_template(
                    "n", title="T", message="m", ack_button_text="A" * 30
                )
            with pytest.raises(ValidationError, match="forbid proceed/stop"):
                client.notifications.create_template(
                    "n",
                    title="T",
                    message="m",
                    action_type="block",
                    ack_button_text="OK",
                    proceed_button_text="Go",
                )
            assert route.call_count == 0

    def test_a_valid_create_still_sends_camel_case_fields(self, client: NetskopeClient) -> None:
        with _mock() as mock:
            route = mock.post("/api/v2/notifications/user/templates").mock(
                return_value=httpx.Response(201, json=self._TEMPLATE)
            )
            client.notifications.create_template(
                "Custom Block Page",
                title="Access Denied",
                message="This site is blocked.",
                action_type="block",
                ack_button_text="OK",
            )
        assert json.loads(route.calls.last.request.content) == {
            "name": "Custom Block Page",
            "title": "Access Denied",
            "message": "This site is blocked.",
            "templateActionType": "block",
            "ackButtonText": "OK",
        }

    def test_patch_requires_the_complete_body_and_applies_the_lengths(
        self, client: NetskopeClient
    ) -> None:
        """``PATCH /user/templates/{id}`` points at the same body schema
        (user-notifications-templates.yaml:376-381), so required fields and ``maxLength`` rules
        apply to PATCH as well as POST."""
        with _mock() as mock:
            route = mock.patch("/api/v2/notifications/user/templates/42").mock(
                return_value=httpx.Response(200, json={**self._TEMPLATE, "subtitle": "New"})
            )
            with pytest.raises(ValidationError, match="subtitle"):
                client.notifications.update_template(42, subtitle="S" * 100)
            with pytest.raises(ValidationError, match="name"):
                client.notifications.update_template(42, subtitle="New")
            template = client.notifications.update_template(
                42,
                name="Block",
                title="Denied",
                message="Blocked",
                ack_button_text="OK",
                subtitle="New",
            )
        assert template.subtitle == "New"
        assert json.loads(route.calls.last.request.content) == {
            "name": "Block",
            "title": "Denied",
            "message": "Blocked",
            "ackButtonText": "OK",
            "subtitle": "New",
        }

    async def test_async_writes_apply_the_same_rules(self, aclient: AsyncNetskopeClient) -> None:
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="title"):
                await aclient.notifications.create_template(
                    "n", title="T" * 80, message="m", ack_button_text="OK"
                )
            with pytest.raises(ValidationError, match="stopButtonText"):
                await aclient.notifications.update_template(42, stop_button_text="S" * 30)
            assert route.call_count == 0

    def test_the_typed_write_model_is_unchanged(self) -> None:
        """The typed surface already required the trio and the button rules."""
        with pytest.raises(Exception, match="title"):
            NotificationTemplateWrite(name="n", title="T" * 80, message="m", ackButtonText="OK")


# --- SPEC2-DSPM-1: the legacy reads share the verified route table --------


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("bounds", [(0, 1), (1, 0), (-1, 1)])
async def test_entity_queries_require_positive_epoch_bounds(
    client: NetskopeClient,
    aclient: AsyncNetskopeClient,
    asynchronous: bool,
    typed: bool,
    bounds: tuple[int, int],
) -> None:
    """SPEC2-DEM-9: dem-workbench-query.yaml:324-327,350-353 require epochs > 0."""
    query = (aclient if asynchronous else client).dem.query
    accessor = query.with_response if typed else query
    with _mock() as mock:
        with pytest.raises(ValidationError):
            if asynchronous:
                await accessor.get_entities(start_time=bounds[0], end_time=bounds[1])
            else:
                accessor.get_entities(start_time=bounds[0], end_time=bounds[1])
        assert not mock.calls


class TestDspmLegacyRoutes:
    def test_legacy_list_uses_the_verified_path(self, client: NetskopeClient) -> None:
        """``GET /datastores/connected`` (dspm/dspm_external.yaml) is the route
        both surfaces resolve; the module docstring now says so."""
        with _mock() as mock:
            route = mock.get("/api/v2/dspm/datastores/connected").mock(
                return_value=httpx.Response(200, json={"success": True, "data": {"results": []}})
            )
            client.dspm.list_resources("connected_datastores")
        assert route.call_count == 1

    def test_an_unmapped_resource_name_raises_instead_of_building_a_path(
        self, client: NetskopeClient
    ) -> None:
        with _mock() as mock:
            route = mock.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
            with pytest.raises(ValidationError, match="No verified public DSPM read contract"):
                client.dspm.list_resources("columns")
            assert route.call_count == 0
