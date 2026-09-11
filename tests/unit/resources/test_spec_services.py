"""Gateway-contract conformance for AICC, DEM, IPS, NSIQ, RBI and notifications.

Each test cites the ``production/endpoints`` declaration it pins.  Bodies are
taken from the spec's own examples where one exists, so a response the tenant
really sends decodes without losing fields.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.models.aicc import (
    AiccApplicationQuery,
    AiccDataCoverage,
    AiccExtensionRelatedQuery,
    AiccModelQuery,
    AiccProtectionQuery,
)
from netskope.models.dem import DATA_QUERY_SOURCES, DemAlertRule, DemProbe, QueryDataSource
from netskope.models.notifications import NotificationTemplateWrite
from netskope.models.nsiq import FalsePositiveReceipt, UrlLookupReport
from netskope.models.rbi import RbiApplications
from netskope.resources._aicc_contract import QUERY_RULES
from netskope.resources.dem import AsyncDemResource, DemResource
from netskope.resources.ips import AsyncIpsResource, IpsResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com"
_AICC = f"{_BASE}/api/v2/aicc"
_WINDOW = {"start_time": "2026-08-01T00:00:00Z", "end_time": "2026-08-18T00:00:00Z"}


# --- SPEC-S17: DEM probe and alert-rule records ---------------------------


class TestDemProbeAndAlertRuleRecords:
    """``demconfig.yaml`` and ``dem_alert.yaml`` response shapes decode in full."""

    @respx.mock
    def test_app_probe_row_from_the_spec_example(self, client: NetskopeClient) -> None:
        """``AppProbeGetResp`` (demconfig.yaml:2812), "full result" example (:597-627)."""
        body = {
            "totalCount": 1,
            "data": [
                {
                    "id": 1,
                    "name": "app probe 1",
                    "appID": 1,
                    "appName": "app 1",
                    "appType": "custom",
                    "appDomains": ["domain.com"],
                    "frequency": 10,
                    "priority": 1,
                    "entity": {"user": ["user1"], "group": ["group1"], "ou": ["ou1"]},
                    "os": ["windows", "mac"],
                    "deviceClassification": ["managed", "unmanaged"],
                    "status": 0,
                    "modifiedTime": "2024-05-22T06:45:07.022000Z",
                    "createdTime": "2024-05-22T06:45:07.022000Z",
                }
            ],
        }
        respx.get(f"{_BASE}/api/v2/dem/appprobes").mock(return_value=httpx.Response(200, json=body))

        probes = DemResource(client._transport).probes.with_response.list().parse()

        assert len(probes) == 1
        probe = probes[0]
        assert (probe.app_id, probe.app_name, probe.app_type) == (1, "app 1", "custom")
        assert probe.app_domains == ["domain.com"]
        assert probe.frequency == 10
        assert probe.priority == 1
        assert probe.entity is not None and probe.entity.user == ["user1"]
        assert probe.device_classification == ["managed", "unmanaged"]
        assert probe.status == 0
        # Nothing had to fall through to `extra` to survive.
        assert probe.model_extra == {}

    @respx.mock
    def test_network_probe_collection_flags_decode(self, client: NetskopeClient) -> None:
        """``NetworkProbeCreateUpdateResp`` adds two collection flags (demconfig.yaml:2813)."""
        body = {
            "totalCount": 1,
            "data": [
                {
                    "id": 4,
                    "name": "network probe",
                    "networkPathDeviceHealthCollection": True,
                    "processInfoCollection": False,
                    "frequency": 5,
                    "os": ["windows"],
                    "deviceClassification": ["not configured"],
                    "status": 1,
                }
            ],
        }
        respx.get(f"{_BASE}/api/v2/dem/networkprobes").mock(
            return_value=httpx.Response(200, json=body)
        )

        probes = DemResource(client._transport).network_probes.with_response.list().parse()

        assert probes[0].network_path_device_health_collection is True
        assert probes[0].process_info_collection is False
        assert probes[0].model_extra == {}

    @respx.mock
    def test_alert_rules_envelope_carries_remaining_quota(self, client: NetskopeClient) -> None:
        """``GET /alert/rules`` answers ``{remainingQuota, rules, totalCount}``
        (dem_alert.yaml:1289-1330), and a rule keeps its criteria."""
        criteria = {
            "condition": {
                "measure": "userDemScore",
                "thresholds": {"threshold": {"le": {"score": 50}}},
                "window": 300,
            },
            "duration": 600,
        }
        body = {
            "remainingQuota": 9,
            "totalCount": 1,
            "rules": [
                {
                    "id": "rule-1",
                    "name": "Experience drop",
                    "category": "User Experience",
                    "type": "Experience Score",
                    "criteria": criteria,
                    "criteriaType": "event",
                    "emailReceiver": "ops@example.test",
                    "enabled": True,
                    "severity": "high",
                    "webhookReceivers": [{"id": "recv-1"}],
                    "lastUpdateTime": 1722052800,
                    "numOfAlerts": 2,
                }
            ],
        }
        route = respx.get(f"{_BASE}/api/v2/dem/alert/rules").mock(
            return_value=httpx.Response(200, json=body)
        )

        response = DemResource(client._transport).alert_rules.with_response.list()
        rules = response.parse()

        assert response.json()["remainingQuota"] == 9
        assert len(rules) == 1
        rule = rules[0]
        assert rule.criteria == criteria
        assert rule.criteria_type == "event"
        assert rule.email_receiver == "ops@example.test"
        assert rule.webhook_receivers[0].id == "recv-1"
        assert rule.last_update_time == 1722052800
        assert rule.num_of_alerts == 2
        assert rule.model_extra == {}
        assert not route.calls.last.request.url.params

    def test_models_no_longer_declare_fields_the_api_never_returns(self) -> None:
        """The retired fields are gone, so a caller cannot read a permanent ``None``."""
        assert not {"target", "protocol", "interval"} & set(DemProbe.model_fields)
        assert not {"metric", "threshold", "probe_id"} & set(DemAlertRule.model_fields)


# --- SPEC-S25 / S26: DEM query inputs -------------------------------------


class TestDemQueryInputs:
    def test_data_query_sources_exclude_the_state_sources(self) -> None:
        """``DataQueryFrom`` is the 16-value set (dem-workbench-query.yaml:15-33);
        ``agent_status``/``client_status`` belong to ``StateQueryFrom`` (:516-521)."""
        assert len(DATA_QUERY_SOURCES) == 16
        assert QueryDataSource.AGENT_STATUS not in DATA_QUERY_SOURCES
        assert QueryDataSource.CLIENT_STATUS not in DATA_QUERY_SOURCES

    @respx.mock
    def test_get_entities_sends_sortby_and_user_location(self, client: NetskopeClient) -> None:
        """``/query/getentities`` declares ``sortby`` (dem-workbench-query.yaml:1229-1236)
        and its body accepts ``userLocation`` (:1260-1263)."""
        route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
            return_value=httpx.Response(200, json={"users": []})
        )

        DemResource(client._transport).query.get_entities(
            start_time=1689490800,
            end_time=1689577200,
            user_location=[{"city": "San Francisco", "country": "USA", "region": "CA"}],
            sort_by="user_score",
            sort_order="asc",
            limit=10,
        )

        assert dict(route.calls.last.request.url.params) == {
            "limit": "10",
            "sortby": "user_score",
            "sortorder": "asc",
        }
        assert sent_json(route)["userLocation"] == [
            {"city": "San Francisco", "country": "USA", "region": "CA"}
        ]

    @respx.mock
    async def test_get_entities_sortby_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE}/api/v2/dem/query/getentities").mock(
            return_value=httpx.Response(200, json={"users": []})
        )

        await AsyncDemResource(aclient._transport).query.get_entities(
            start_time=1689490800, end_time=1689577200, sort_by="user_score"
        )

        assert dict(route.calls.last.request.url.params) == {"sortby": "user_score"}


# --- SPEC-S19: IPS sort parameters ----------------------------------------


class TestIpsSorting:
    @respx.mock
    def test_signature_overrides_send_sortby_and_sortorder(self, client: NetskopeClient) -> None:
        """``GET /signatureoverrides`` declares both (ips/ms-ips.yaml:1186-1206)."""
        route = respx.get(f"{_BASE}/api/v2/ips/signatureoverrides").mock(
            return_value=httpx.Response(200, json={"status": "Success", "data": {}})
        )

        IpsResource(client._transport).list_signature_overrides(
            limit=25, offset=3, sort_by="name", sort_order="desc"
        )

        assert dict(route.calls.last.request.url.params) == {
            "limit": "25",
            "offset": "3",
            "sortby": "name",
            "sortorder": "desc",
        }

    @respx.mock
    def test_signature_search_body_carries_the_sort_fields(self, client: NetskopeClient) -> None:
        """The ``POST /getsignaturelist`` body accepts the same two (ms-ips.yaml:725-741)."""
        route = respx.post(f"{_BASE}/api/v2/ips/getsignaturelist").mock(
            return_value=httpx.Response(200, json={"status": "Success", "data": {}})
        )

        IpsResource(client._transport).search_signatures(
            limit=32, sort_by="sig_id", sort_order="asc", traffic_type=["web"]
        )

        assert sent_json(route) == {
            "limit": 32,
            "sortby": "sig_id",
            "sortorder": "asc",
            "filter": {"traffic_type": ["web"]},
        }

    @respx.mock
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"sort_by": "severity"}, "sort_by must be one of"),
            ({"sort_order": "down"}, "sort_order must be one of"),
        ],
    )
    def test_sort_values_outside_the_enum_never_reach_the_wire(
        self, client: NetskopeClient, kwargs: dict[str, str], message: str
    ) -> None:
        route = respx.route(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        ips = IpsResource(client._transport)
        with pytest.raises(ValidationError, match=message):
            ips.list_signature_overrides(**kwargs)
        with pytest.raises(ValidationError, match=message):
            ips.search_signatures(**kwargs)
        assert route.call_count == 0

    @respx.mock
    async def test_signature_overrides_sorting_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/api/v2/ips/signatureoverrides").mock(
            return_value=httpx.Response(200, json={"status": "Success", "data": {}})
        )

        await AsyncIpsResource(aclient._transport).list_signature_overrides(sort_by="sig_id")

        assert dict(route.calls.last.request.url.params) == {"sortby": "sig_id"}


# --- SPEC-S21 / S22: AICC contract enums and optional coverage ------------


class TestAiccContract:
    @respx.mock
    @pytest.mark.parametrize(
        ("collection", "path", "query", "message"),
        [
            (
                "applications",
                "inventory/ai-applications",
                AiccApplicationQuery(**_WINDOW, risk_level=["Severe"]),
                "reconciled_risk_level",
            ),
            (
                "models",
                "inventory/models",
                AiccModelQuery(**_WINDOW, deployment=["serverless"]),
                "deployment",
            ),
        ],
    )
    def test_array_enums_are_checked_element_by_element(
        self, collection: str, path: str, query: object, message: str
    ) -> None:
        """``ReconciledRiskLevel`` (aicc/inventory.yaml:6851) and the ``deployment``
        enum (:3902-3914) constrain each array element."""
        route = respx.get(f"{_AICC}/{path}").mock(return_value=httpx.Response(200, json={}))
        with (
            NetskopeClient(tenant="t.goskope.com", api_token="tok") as client,
            pytest.raises(ValidationError, match=message),
        ):
            getattr(client.aicc, collection).list_page(query)
        assert route.call_count == 0

    @respx.mock
    def test_accepted_enum_values_reach_the_wire(self) -> None:
        route = respx.get(f"{_AICC}/inventory/ai-applications").mock(
            return_value=httpx.Response(200, json={"data": {"total": 0, "items": []}})
        )
        with NetskopeClient(tenant="t.goskope.com", api_token="tok") as client:
            client.aicc.applications.list_page(
                AiccApplicationQuery(**_WINDOW, risk_level=["Critical", "High"])
            )
        params = route.calls.last.request.url.params
        assert params.get_list("reconciled_risk_level") == ["Critical", "High"]

    @pytest.mark.parametrize(
        ("contract", "name", "expected"),
        [
            (
                "/inventory/extensions/{extension_name}/identities",
                "type",
                ("browser_extension", "editor_extension", "desktop_extension"),
            ),
            (
                "/inventory/models",
                "deployment",
                ("cloud", "endpoint", "self_hosted_vm", "self_hosted_k8s"),
            ),
            (
                "/provider/{provider}/data-protection/violations",
                "severity",
                ("critical", "high", "medium", "low"),
            ),
            (
                "/analytics/identities",
                "reconciled_risk_level",
                (
                    "Critical",
                    "High",
                    "Medium",
                    "Low",
                    "Inconclusive",
                    "Legitimate",
                    "Unknown",
                ),
            ),
        ],
    )
    def test_contract_carries_the_spec_enumerations(
        self, contract: str, name: str, expected: tuple[str, ...]
    ) -> None:
        """aicc/inventory.yaml:1521-1531, :3902-3914, :3752-3763 and :6851-6853."""
        choices = {rule[0]: rule[3] for rule in QUERY_RULES[contract]}
        assert choices[name] == expected

    @pytest.mark.parametrize(
        ("model", "kwargs"),
        [
            (AiccExtensionRelatedQuery, {"type": "kernel_extension"}),
            (AiccProtectionQuery, {"severity": ["catastrophic"]}),
        ],
    )
    def test_scalar_enums_are_refused_by_the_query_contract(
        self, model: type, kwargs: dict[str, object]
    ) -> None:
        with pytest.raises(ModelValidationError):
            model(**_WINDOW, **kwargs)

    def test_data_coverage_tolerates_a_missing_timestamp(self) -> None:
        """``data_available_since`` is nullable with no required list (:5978-5981)."""
        assert AiccDataCoverage.model_validate({}).data_available_since is None
        assert (
            AiccDataCoverage.model_validate({"data_available_since": None}).data_available_since
            is None
        )


# --- SPEC-S23 / S24 / S27: optional response fields -----------------------


class TestOptionalResponseFields:
    def test_url_lookup_report_survives_a_sparse_row(self) -> None:
        """``url-lookup-report`` declares no required properties (nsiq/url_lookup.yaml)."""
        report = UrlLookupReport.model_validate({"site": "netskope"})
        assert report.url is None and report.site == "netskope"

    def test_false_positive_receipt_survives_a_sparse_row(self) -> None:
        """``FPCaseInfo``/``FPTicketInfo`` declare no required properties
        (nsiq/fp_submission.yaml:30-55)."""
        receipt = FalsePositiveReceipt.model_validate({"tickets": [{"system": "jira"}]})
        assert receipt.incident_id is None
        assert receipt.tickets[0].ticket_id is None
        assert receipt.tickets[0].system == "jira"

    @pytest.mark.parametrize("color", ["#A659B1", "#ABC", "#RRGGBBAA", "rebeccapurple"])
    def test_stripe_color_is_a_free_form_string(self, color: str) -> None:
        """``stripeColor`` is a bare string with no pattern
        (user-notifications-templates.yaml:62-64)."""
        template = NotificationTemplateWrite(
            name="Block",
            title="Access Denied",
            message="Blocked by policy.",
            ackButtonText="OK",
            stripeColor=color,
        )
        assert template.stripe_color == color

    def test_rbi_applications_tolerates_a_missing_collection(self) -> None:
        """Only ``message`` and ``status`` are required (rbi/templates.yaml:7)."""
        body = RbiApplications.model_validate({"status": "success", "message": "ok"})
        assert body.applications == {}
