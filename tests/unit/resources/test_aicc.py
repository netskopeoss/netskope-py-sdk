"""AICC typed operations and checked pagination use one SDK transport."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import ValidationError as ModelValidationError

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import PaginationError, ResponseValidationError, ValidationError
from netskope.models.aicc import (
    AiccAgentQuery,
    AiccApplicationQuery,
    AiccDataCoverage,
    AiccExtensionRelatedQuery,
    AiccIdentityQuery,
    AiccMcpQuery,
    AiccModelQuery,
    AiccProtectionQuery,
    AiccSort,
)
from netskope.resources.shared.aicc_contract import QUERY_RULES

BASE = "https://test.goskope.com/api/v2/aicc"
WINDOW = {"start_time": "2026-08-01T00:00:00Z", "end_time": "2026-08-18T00:00:00Z"}


def test_collection_exposes_its_validated_record_key():
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        assert client.aicc.applications.records_key == "items"
        assert client.aicc.data_protection("anthropic").violations.records_key == "violations"


async def test_async_collection_exposes_its_validated_record_key():
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        assert client.aicc.applications.records_key == "items"
        assert client.aicc.data_protection("anthropic").violations.records_key == "violations"


@pytest.mark.parametrize("name", [".", ".."])
@pytest.mark.parametrize(
    "namespace", ["application", "mcp_server", "identity", "model", "agent", "extension"]
)
@respx.mock
async def test_entity_names_cannot_change_the_resource_path(name, namespace):
    with (
        NetskopeClient(tenant="test.goskope.com", api_token="token") as client,
        pytest.raises(ValidationError, match="relative path"),
    ):
        getattr(client.aicc, namespace)(name)
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as async_client:
        with pytest.raises(ValidationError, match="relative path"):
            getattr(async_client.aicc, namespace)(name)
    assert not respx.calls


READS = [
    ("data_coverage", "data-coverage", {"data_available_since": None}, {}),
    (
        "analytics.entity_counts",
        "analytics/entity-counts",
        {"applications": 1, "users": 2, "unknown": 0},
        WINDOW,
    ),
    (
        "analytics.counts",
        "analytics/counts",
        {"value": "007", "data": []},
        {**WINDOW, "type": "alerts"},
    ),
    ("analytics.sums", "analytics/sums", {"value": 5, "data": []}, {**WINDOW, "type": "traffic"}),
    (
        "analytics.breakdown_apps",
        "analytics/ai-applications",
        {"segments": [{"label": "High", "value": 2}]},
        {**WINDOW, "dimension": "ccl"},
    ),
    (
        "analytics.breakdown_mcp",
        "analytics/mcp-servers",
        {"segments": []},
        {**WINDOW, "dimension": "ccl"},
    ),
    (
        "analytics.breakdown_identities",
        "analytics/identities",
        {"segments": []},
        {**WINDOW, "dimension": "ou"},
    ),
    (
        "analytics.breakdown_models",
        "analytics/models",
        {"segments": []},
        {**WINDOW, "dimension": "provider"},
    ),
    (
        "analytics.breakdown_agents",
        "analytics/agents",
        {"segments": []},
        {**WINDOW, "dimension": "framework"},
    ),
    (
        "analytics.alerts_matrix",
        "analytics/alerts/matrix",
        {"items": [{"asset": "AI App", "detection": "DLP", "count": 2}]},
        WINDOW,
    ),
    (
        "analytics.alert_policies",
        "analytics/alerts/policies",
        {"items": [{"policy": "PII", "severity": "critical", "count": 2}]},
        WINDOW,
    ),
    (
        "application|A/B App.details",
        "inventory/ai-applications/A%2FB%20App",
        {"metadata": {"name": "A/B App"}},
        WINDOW,
    ),
    (
        "application|ChatGPT.status",
        "inventory/ai-applications/ChatGPT/status",
        {"name": "ChatGPT", "cci_score": "082"},
        {},
    ),
    (
        "mcp_server|server.details",
        "inventory/mcp-servers/server",
        {"metadata": {"name": "server"}},
        WINDOW,
    ),
    (
        "identity|a@example.com.details",
        "inventory/identities/a%40example.com",
        {"metadata": {"user_id": "a@example.com", "type": "user"}},
        WINDOW,
    ),
    ("model|model.details", "inventory/models/model", {"metadata": {"name": "model"}}, WINDOW),
    ("agent|agent.details", "inventory/agents/agent", {"metadata": {"name": "agent"}}, WINDOW),
    (
        "extension|extension.details",
        "inventory/extensions/extension",
        {"metadata": {"name": "extension"}},
        WINDOW,
    ),
    (
        "application|ChatGPT.traffic_trend",
        "inventory/ai-applications/ChatGPT/traffic-trend",
        {"resolution": "1d", "data": []},
        WINDOW,
    ),
    (
        "application|ChatGPT.identity_trend",
        "inventory/ai-applications/ChatGPT/identity-trend",
        {"resolution": "1d", "data": []},
        WINDOW,
    ),
    (
        "application|ChatGPT.risk_trend",
        "inventory/ai-applications/ChatGPT/risk-trend",
        {"data": []},
        WINDOW,
    ),
    (
        "data_protection|anthropic.summary",
        "provider/anthropic/data-protection/summary",
        {"breakdown": []},
        WINDOW,
    ),
]

COLLECTIONS = [
    (
        "applications",
        "inventory/ai-applications",
        {"name": "App", "sessions": "007"},
        WINDOW,
        "items",
    ),
    ("mcp_servers", "inventory/mcp-servers", {"name": "server", "events": 2}, WINDOW, "items"),
    ("identities", "inventory/identities", {"user_id": "a", "type": "user"}, WINDOW, "items"),
    ("models", "inventory/models", {"name": "model"}, WINDOW, "items"),
    ("agents", "inventory/agents", {"name": "agent"}, WINDOW, "items"),
    (
        "application|App.identities",
        "inventory/ai-applications/App/identities",
        {"name": "a"},
        WINDOW,
        "items",
    ),
    (
        "application|App.deployments",
        "inventory/ai-applications/App/deployments",
        {"name": "cloud", "type": "cloud_web"},
        {**WINDOW, "type": "cloud_web"},
        "items",
    ),
    (
        "application|App.violations",
        "inventory/ai-applications/App/violations",
        {"policy_name": "PII", "severity": "high"},
        WINDOW,
        "items",
    ),
    (
        "mcp_server|server.identities",
        "inventory/mcp-servers/server/identities",
        {"name": "a"},
        WINDOW,
        "items",
    ),
    (
        "mcp_server|server.deployments",
        "inventory/mcp-servers/server/deployments",
        {"name": "cloud", "type": "cloud"},
        {**WINDOW, "type": "cloud"},
        "items",
    ),
    (
        "mcp_server|server.violations",
        "inventory/mcp-servers/server/violations",
        {"policy_name": "PII", "severity": "high"},
        {**WINDOW, "status": "current"},
        "items",
    ),
    ("identity|a.agents", "inventory/identities/a/agents", {"name": "agent"}, WINDOW, "items"),
    ("identity|a.models", "inventory/identities/a/models", {"name": "model"}, WINDOW, "items"),
    (
        "identity|a.mcp_servers",
        "inventory/identities/a/mcp-servers",
        {"name": "server"},
        WINDOW,
        "items",
    ),
    ("model|model.identities", "inventory/models/model/identities", {"name": "a"}, WINDOW, "items"),
    (
        "model|model.deployments",
        "inventory/models/model/deployments",
        {"name": "vm", "type": "self_hosted_vm"},
        {**WINDOW, "type": "self_hosted_vm"},
        "items",
    ),
    ("agent|agent.identities", "inventory/agents/agent/identities", {"name": "a"}, WINDOW, "items"),
    (
        "agent|agent.deployments",
        "inventory/agents/agent/deployments",
        {"name": "vm", "type": "vm"},
        {**WINDOW, "type": "vm"},
        "items",
    ),
    (
        "extension|extension.identities",
        "inventory/extensions/extension/identities",
        {"name": "a"},
        WINDOW,
        "items",
    ),
    (
        "extension|extension.deployments",
        "inventory/extensions/extension/deployments",
        {"name": "ext", "type": "browser_extension"},
        {**WINDOW, "type": "browser_extension"},
        "items",
    ),
    (
        "data_protection|anthropic.violations",
        "provider/anthropic/data-protection/violations",
        {"severity": "high", "violation": "PII"},
        WINDOW,
        "violations",
    ),
]


def operation(client, selector):
    current = client.aicc
    if "|" in selector:
        factory, rest = selector.split("|", 1)
        name, selector = rest.rsplit(".", 1)
        current = getattr(current, factory)(name)
    for attr in selector.split("."):
        current = getattr(current, attr)
    return current


@pytest.mark.parametrize(("selector", "path", "payload", "params"), READS)
@respx.mock
def test_reads(selector, path, payload, params):
    body = {"success": True, "data": payload}
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = operation(client, selector)
        response = endpoint.with_response.get(endpoint.query_type.model_validate(params))
        assert response.parse() is response.parse()
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize(("selector", "path", "payload", "params"), READS)
@respx.mock
async def test_async_reads(selector, path, payload, params):
    body = {"success": True, "data": payload}
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = operation(client, selector)
        response = await endpoint.with_response.get(endpoint.query_type.model_validate(params))
        assert response.parse() is response.parse()
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize(("selector", "path", "item", "params", "key"), COLLECTIONS)
@respx.mock
def test_collection(selector, path, item, params, key):
    body = {"success": True, "data": {key: [item], "total": "1", "offset": 0}}
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = operation(client, selector)
        response = endpoint.with_response.list_page(endpoint.query_type.model_validate(params))
        page = response.parse()
        assert len(page.items) == 1
        assert page.total == 1
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize(("selector", "path", "item", "params", "key"), COLLECTIONS)
@respx.mock
async def test_async_collection(selector, path, item, params, key):
    body = {"success": True, "data": {key: [item], "total": 1, "offset": 0}}
    route = respx.get(f"{BASE}/{path}").respond(200, json=body)
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = operation(client, selector)
        response = await endpoint.with_response.list_page(
            endpoint.query_type.model_validate(params)
        )
        assert response.parse().total == 1
        assert response.json() == body
    assert route.call_count == 1


def app_page(names, *, total, offset):
    return httpx.Response(
        200,
        json={
            "data": {"items": [{"name": name} for name in names], "total": total, "offset": offset}
        },
    )


async def scan_applications(asynchronous, **options):
    """Drain the application scan through whichever client flavor is under test."""
    if asynchronous:
        async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            return [
                page
                async for page in client.aicc.applications.iter_pages(
                    AiccApplicationQuery(**WINDOW), **options
                )
            ]
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        return list(client.aicc.applications.iter_pages(AiccApplicationQuery(**WINDOW), **options))


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_short_page_does_not_override_known_total(asynchronous):
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        side_effect=[
            app_page(["a"], total=2, offset=0),
            app_page(["b"], total=2, offset=1),
        ]
    )
    pages = await scan_applications(asynchronous, page_size=100)
    assert [page.items[0].name for page in pages] == ["a", "b"]
    assert route.calls[1].request.url.params["offset"] == "1"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("second", "match"),
    [
        (app_page(["a"], total=2, offset=1), "repeated"),
        (app_page([], total=2, offset=1), "empty page"),
        (app_page(["b"], total=3, offset=1), "total changed"),
        (app_page(["b"], total=2, offset=0), "offset"),
    ],
)
@respx.mock
async def test_unsafe_continuation(asynchronous, second, match):
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        side_effect=[app_page(["a"], total=2, offset=0), second]
    )
    with pytest.raises(PaginationError, match=match):
        await scan_applications(asynchronous, page_size=1)
    assert route.call_count == 2


@respx.mock
async def test_async_prefix_is_deliberate_and_bounded():
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        side_effect=[
            app_page(["a", "b"], total=10, offset=0),
            app_page(["c"], total=10, offset=2),
        ]
    )
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        pages = [
            page
            async for page in client.aicc.applications.iter_pages(
                AiccApplicationQuery(**WINDOW),
                page_size=2,
                stop_after=3,
            )
        ]
    assert sum(len(page.items) for page in pages) == 3
    assert route.calls.last.request.url.params["limit"] == "1"


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_hard_scan_limit_is_not_an_exact_total(asynchronous):
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        return_value=app_page(["a"], total=10, offset=0)
    )
    with pytest.raises(PaginationError, match="safety limit"):
        await scan_applications(asynchronous, max_records=1)
    assert route.call_count == 1


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_scan_bounds_are_reported_under_their_own_names(asynchronous):
    with pytest.raises(ValidationError, match="stop_after must be a positive integer"):
        await scan_applications(asynchronous, stop_after=0)
    with pytest.raises(ValidationError, match="page_size must be a positive integer"):
        await scan_applications(asynchronous, page_size=0)
    assert not respx.calls


@respx.mock
def test_query_aliases_and_sort_are_serialized_by_sdk():
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        return_value=app_page([], total=0, offset=0)
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        client.aicc.applications.list_page(
            AiccApplicationQuery(
                **WINDOW,
                risk_level=["High"],
                sort=AiccSort(field="bytes", order="desc"),
            )
        )
    params = route.calls.last.request.url.params
    assert params["reconciled_risk_level"] == "High"
    assert "risk_level" not in params
    assert json.loads(params["sort"]) == {"field": "bytes", "order": "desc"}


async def scan_violations(asynchronous, **options):
    """Drain the data-protection scan through whichever client flavor is under test."""
    if asynchronous:
        async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            endpoint = client.aicc.data_protection("anthropic").violations
            return [
                page
                async for page in endpoint.iter_pages(
                    endpoint.query_type(**WINDOW, include_total=False), **options
                )
            ]
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = client.aicc.data_protection("anthropic").violations
        return list(
            endpoint.iter_pages(endpoint.query_type(**WINDOW, include_total=False), **options)
        )


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_include_total_false_is_page_local_not_collection_total(asynchronous):
    route = respx.get(f"{BASE}/provider/anthropic/data-protection/violations").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": {
                        "violations": [{"severity": "high", "violation": "a"}],
                        "total": 1,
                        "offset": 0,
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": {
                        "violations": [{"severity": "high", "violation": "b"}],
                        "total": 1,
                        "offset": 1,
                    }
                },
            ),
            httpx.Response(200, json={"data": {"violations": [], "total": 0, "offset": 2}}),
        ]
    )
    pages = await scan_violations(asynchronous, page_size=1)
    assert [page.total for page in pages] == [None, None, None]
    assert route.call_count == 3


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("lost_total", [None, "omitted"])
@respx.mock
async def test_remembered_total_prevents_early_termination(asynchronous, lost_total):
    middle = {"items": [{"name": "b"}], "offset": 1}
    if lost_total is None:
        middle["total"] = None
    route = respx.get(f"{BASE}/inventory/ai-applications").mock(
        side_effect=[
            app_page(["a"], total=3, offset=0),
            httpx.Response(200, json={"data": middle}),
            app_page(["c"], total=3, offset=2),
        ]
    )
    pages = await scan_applications(asynchronous, page_size=100)
    assert sum(len(page.items) for page in pages) == 3
    assert route.call_count == 3


@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_empty_page_cannot_discard_earlier_total(asynchronous):
    respx.get(f"{BASE}/inventory/ai-applications").mock(
        side_effect=[
            app_page(["a"], total=3, offset=0),
            httpx.Response(200, json={"data": {"items": [], "offset": 1}}),
        ]
    )
    with pytest.raises(PaginationError, match="empty page"):
        await scan_applications(asynchronous, page_size=100)


@respx.mock
def test_invalid_operation_options_never_request():
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        query = AiccApplicationQuery(**WINDOW)
        with pytest.raises(ValidationError):
            client.aicc.applications.list_page(query, limit=201)
        endpoint = client.aicc.application("App").deployments
        deployment = endpoint.query_type(**WINDOW, type="endpoint")
        with pytest.raises(ValidationError, match="does not support"):
            endpoint.list_page(deployment, limit=1)
        endpoint = client.aicc.analytics.breakdown_mcp
        with pytest.raises(ValidationError, match="metric"):
            endpoint.get(endpoint.query_type(**WINDOW, dimension="ccl", metric="bytes"))
    assert not respx.calls


@respx.mock
def test_bad_schema_keeps_original_bytes_private_from_error():
    body = {"data": {"items": [{"name": "app", "sessions": "sensitive-invalid"}], "total": 1}}
    respx.get(f"{BASE}/inventory/ai-applications").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        response = client.aicc.applications.with_response.list_page(AiccApplicationQuery(**WINDOW))
        with pytest.raises(ResponseValidationError) as caught:
            response.parse()
        assert "sensitive-invalid" not in str(caught.value)
        assert response.json() == body


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("window", [{}, WINDOW])
@respx.mock
async def test_application_status_sends_its_optional_window(asynchronous, window):
    route = respx.get(f"{BASE}/inventory/ai-applications/ChatGPT/status").respond(
        200, json={"data": {"name": "ChatGPT", "status": "sanctioned"}}
    )
    if asynchronous:
        async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            endpoint = client.aicc.application("ChatGPT").status
            result = await endpoint.get(endpoint.query_type.model_validate(window))
    else:
        with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            endpoint = client.aicc.application("ChatGPT").status
            result = endpoint.get(endpoint.query_type.model_validate(window))
    assert result.status == "sanctioned"
    assert dict(route.calls[0].request.url.params) == window


@pytest.mark.parametrize(
    ("collection", "path"),
    [
        ("applications", "inventory/ai-applications"),
        ("mcp_servers", "inventory/mcp-servers"),
        ("identities", "inventory/identities"),
    ],
)
@respx.mock
def test_risk_level_is_sent_under_its_api_parameter_name(collection, path):
    route = respx.get(f"{BASE}/{path}").mock(
        return_value=httpx.Response(200, json={"data": {"items": [], "total": 0, "offset": 0}})
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = getattr(client.aicc, collection)
        endpoint.list_page(endpoint.query_type(**WINDOW, risk_level=["High"]))
    params = route.calls.last.request.url.params
    assert params["reconciled_risk_level"] == "High"
    assert "risk_level" not in params


@pytest.mark.parametrize(
    ("collection", "field"),
    [
        ("applications", "category"),
        ("applications", "status"),
        ("applications", "ccl"),
        ("applications", "risk_level"),
        ("mcp_servers", "ccl"),
        ("identities", "user_group"),
        ("models", "provider"),
        ("agents", "framework"),
    ],
)
@respx.mock
def test_empty_list_filters_are_rejected_rather_than_dropped(collection, field):
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        endpoint = getattr(client.aicc, collection)
        with pytest.raises(ModelValidationError):
            endpoint.query_type(**WINDOW, **{field: []})
    assert not respx.calls


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.

_BASE = "https://t.goskope.com"
_AICC = f"{_BASE}/api/v2/aicc"
_WINDOW = {"start_time": "2026-08-01T00:00:00Z", "end_time": "2026-08-18T00:00:00Z"}


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


def test_first_seen_after_is_declared_only_where_the_endpoint_takes_it():
    """Four inventory endpoints declare ``first_seen_after``; mcp-servers does not.

    ``aicc/inventory.yaml`` declares the parameter on ``/inventory/ai-applications``,
    ``/inventory/identities``, ``/inventory/models`` and ``/inventory/agents``, and
    not on ``/inventory/mcp-servers``, whose parameter list ends at ``active_only``.
    Carrying the field on the shared base gave ``AiccMcpQuery`` a field the SDK
    then refused at request time: the query model should not offer it at all.
    """
    for accepting in (AiccApplicationQuery, AiccIdentityQuery, AiccModelQuery, AiccAgentQuery):
        assert "first_seen_after" in accepting.model_fields, accepting.__name__

    assert "first_seen_after" not in AiccMcpQuery.model_fields
    with pytest.raises(ModelValidationError):
        AiccMcpQuery(**WINDOW, first_seen_after="2026-08-01T00:00:00Z")


def test_the_contract_table_agrees_with_the_query_models():
    """Every inventory list rule names the parameters its query model offers."""
    pairs = (
        ("/inventory/ai-applications", AiccApplicationQuery),
        ("/inventory/identities", AiccIdentityQuery),
        ("/inventory/models", AiccModelQuery),
        ("/inventory/agents", AiccAgentQuery),
        ("/inventory/mcp-servers", AiccMcpQuery),
    )
    for path, model in pairs:
        allowed = {name for name, *_ in QUERY_RULES[path]}
        assert ("first_seen_after" in allowed) == ("first_seen_after" in model.model_fields), path
