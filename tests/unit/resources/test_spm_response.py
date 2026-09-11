"""SPM typed responses retain their completed HTTP payload without another request."""

from __future__ import annotations

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ResponseValidationError

CASES = [
    (
        "list_apps",
        "GET",
        "apps",
        {"data": [{"name": "Box", "posture_score": "007"}]},
        {},
        lambda parsed: [(app.name, app.posture_score) for app in parsed] == [("Box", 7)],
    ),
    (
        "get_app",
        "GET",
        "apps/Box",
        {"data": {"name": "Box", "future": [None, 1]}},
        {"app_name": "Box"},
        lambda parsed: parsed.name == "Box" and parsed.model_extra["future"] == [None, 1],
    ),
    (
        "inventory",
        "POST",
        "inventory",
        {"data": [{"resource_id": "r1", "resource_type": "bucket"}]},
        {},
        lambda parsed: parsed[0].resource_id == "r1" and parsed[0].resource_type == "bucket",
    ),
    (
        "posture_score",
        "GET",
        "saas_posture_score",
        {"data": {"posture_score": "082"}},
        {},
        lambda parsed: parsed.posture_score == 82,
    ),
    (
        "list_policy_rules",
        "GET",
        "policy/rules",
        {"data": [{"name": "MFA", "severity": "High"}]},
        {},
        lambda parsed: [(rule.name, rule.severity) for rule in parsed] == [("MFA", "High")],
    ),
    (
        "recent_changes",
        "GET",
        "apps/recentchanges/getstats",
        {"trends": {"samples": [{"timestamp": 1722052800, "posture_confidence_index": 4}]}},
        {},
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
    if method == "POST":
        assert route.calls.last.request.content == b""


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
    body = {"data": [{"name": "Box", "posture_score": "sensitive-invalid"}]}
    respx.get("https://test.goskope.com/api/v2/spm/apps").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        response = client.spm.with_response.list_apps()
        with pytest.raises(ResponseValidationError) as caught:
            response.parse()
        assert "sensitive-invalid" not in str(caught.value)
        assert response.json() == body


@respx.mock
def test_inventory_body_and_typed_rows():
    route = respx.post("https://test.goskope.com/api/v2/spm/inventory").respond(
        200, json={"data": [{"resource_id": "r1", "future": {"enabled": False}}]}
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="test-token") as client:
        rows = client.spm.with_response.inventory(filter="app:Box").parse()
        assert rows[0].resource_id == "r1"
        assert rows[0].model_extra == {"future": {"enabled": False}}
    assert route.calls.last.request.content == b'{"filter":"app:Box"}'
