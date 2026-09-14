"""SPM typed responses retain their completed HTTP payload without another request.

Every case below decodes a body shaped like the one its operation declares in
``production/endpoints/spm``: ``ResourceAggregationResponse``
(inventory.yaml:386-452), ``PostureScoreResponse``
(saas_posture_score.yaml:105-142), ``RulesSummaryList`` (policy.yaml,
``GET /rules/list``) and ``RecentChangesResponse`` (apps.yaml:650).
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ResponseValidationError
from netskope.models.spm import SpmInstanceScore, SpmTrendSample
from tests.unit.resources.conftest import contract_router

_INVENTORY_ROWS = {
    "data": [
        {
            "instance_name": "triremeresearch.onmicrosoft.com",
            "app_suite": "AzureAD",
            "failed_rules": 3,
            "passed_rules": 12,
        }
    ],
    "next_offset": -1,
    "total_count": 1,
}

CASES = [
    (
        "list_apps",
        "POST",
        "inventory/getresources",
        _INVENTORY_ROWS,
        {},
        lambda parsed: (
            [(row.instance_name, row.failed_rules) for row in parsed]
            == [("triremeresearch.onmicrosoft.com", 3)]
        ),
    ),
    (
        "get_app",
        "POST",
        "inventory/getresources",
        {"data": [{"resource_type": "Policies", "app_name": "AzureAD", "total_resources": 4}]},
        {"app_name": "AzureAD"},
        lambda parsed: parsed[0].resource_type == "Policies" and parsed[0].total_resources == 4,
    ),
    (
        "inventory",
        "POST",
        "inventory/getresources",
        {"data": [{"resource_id": "r1", "resource_type": "bucket"}]},
        {},
        lambda parsed: parsed[0].resource_id == "r1" and parsed[0].resource_type == "bucket",
    ),
    (
        "posture_score",
        "POST",
        "results/getposturescores",
        {
            "score": {"posture_confidence_index": 60, "posture_confidence_level": "Medium"},
            "app_suites": [
                {
                    "name": "Microsoft365",
                    "score": {"posture_risk_score": 40},
                    "instances": [
                        {"name": "m365", "apps": [{"name": "Defender", "score": {}}]},
                    ],
                }
            ],
        },
        {},
        lambda parsed: (
            parsed.score.posture_confidence_index == 60
            and parsed.app_suites[0].instances[0].apps[0].name == "Defender"
        ),
    ),
    (
        "list_policy_rules",
        "GET",
        "rules/list",
        {"rules": [{"id": "7", "name": "MFA", "appsuite": "AzureAD", "type": "Predefined"}]},
        {},
        lambda parsed: [(rule.name, rule.type) for rule in parsed] == [("MFA", "Predefined")],
    ),
    (
        "recent_changes",
        "POST",
        "apps/recentchanges/getstats",
        {"trends": {"samples": [{"timestamp": 1722052800, "posture_confidence_index": 4}]}},
        {"start": 1722052800, "end": 1722139200},
        lambda parsed: (
            parsed.trends.samples[0].timestamp == 1722052800
            and parsed.trends.samples[0].posture_confidence_index == 4
        ),
    ),
]


@pytest.mark.parametrize(("name", "method", "path", "body", "kwargs", "check"), CASES)
@respx.mock
def test_sync(name, method, path, body, kwargs, check):
    route = respx.route(method=method, url=f"https://test.goskope.com/api/v2/spm/{path}").respond(
        200, json=body
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        response = getattr(client.spm.with_response, name)(**kwargs)
        parsed = response.parse()
        assert check(parsed)
        assert response.parse() is parsed
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize(("name", "method", "path", "body", "kwargs", "check"), CASES)
@respx.mock
async def test_async(name, method, path, body, kwargs, check):
    route = respx.route(method=method, url=f"https://test.goskope.com/api/v2/spm/{path}").respond(
        200, json=body
    )
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        response = await getattr(client.spm.with_response, name)(**kwargs)
        parsed = response.parse()
        assert check(parsed)
        assert response.parse() is parsed
        assert response.json() == body
    assert route.call_count == 1


@respx.mock
def test_schema_error_does_not_discard_original_response():
    body = {"data": [{"instance_name": "Box", "failed_rules": "sensitive-invalid"}]}
    respx.post("https://test.goskope.com/api/v2/spm/inventory/getresources").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        response = client.spm.with_response.list_apps()
        with pytest.raises(ResponseValidationError) as caught:
            response.parse()
        assert "sensitive-invalid" not in str(caught.value)
        assert response.json() == body


@respx.mock
def test_inventory_body_and_typed_rows():
    """``filter`` is the deprecated alias for the operation's own ``ngl_query``."""
    route = respx.post("https://test.goskope.com/api/v2/spm/inventory/getresources").respond(
        200, json={"data": [{"resource_id": "r1", "future": {"enabled": False}}]}
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        rows = client.spm.with_response.inventory(filter="app:Box").parse()
        assert rows[0].resource_id == "r1"
        assert rows[0].model_extra == {"future": {"enabled": False}}
    sent = route.calls.last.request.read()
    assert b'"ngl_query":"app:Box"' in sent
    assert b'"group_by":"resource_name"' in sent


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


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

    def test_sync_parses_a_sample_without_timestamp_or_score(
        self, contract_client: NetskopeClient
    ) -> None:
        with contract_router() as mock:
            mock.post("/api/v2/spm/apps/recentchanges/getstats").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            changes = contract_client.spm.with_response.recent_changes(
                start=1758127874, end=1759127874
            ).parse()
        assert changes.trends is not None
        sample = changes.trends.samples[0]
        assert sample.timestamp is None and sample.posture_confidence_index == 70
        assert sample.posture_scores[0].id == "M365"

    async def test_async_parses_the_same_body(self, contract_aclient: AsyncNetskopeClient) -> None:
        with contract_router() as mock:
            mock.post("/api/v2/spm/apps/recentchanges/getstats").mock(
                return_value=httpx.Response(200, json=self._BODY)
            )
            response = await contract_aclient.spm.with_response.recent_changes(
                start=1758127874, end=1759127874
            )
        changes = response.parse()
        assert changes.trends is not None and changes.trends.samples[0].timestamp is None
