"""RBI reference and template responses validate before presentation."""

from __future__ import annotations

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import PaginationError, ResponseValidationError, ValidationError

TEMPLATE = {
    "template_metadata": {"template_id": "uuid-1", "template_status": "active"},
    "template_data": {"name": "Default", "file_upload": {"enabled": False}},
}
CASES = [
    (
        "list_applications",
        "applications",
        {"applications": {"box": {"appName": "Box", "accounts": ["work"]}}},
        {},
        lambda parsed: (
            parsed.applications["box"].name == "Box"
            and parsed.applications["box"].accounts == ["work"]
        ),
    ),
    (
        "list_supported_browsers",
        "browsers/supported",
        [{"browserName": "Chrome"}],
        {},
        lambda parsed: [browser.name for browser in parsed] == ["Chrome"],
    ),
    (
        "list_default_categories",
        "categories/default",
        [{"appCategory": "Cloud", "category": ["storage"], "activities": ["upload"]}],
        {},
        lambda parsed: (
            parsed[0].name == "Cloud"
            and parsed[0].category == ["storage"]
            and parsed[0].activities == ["upload"]
        ),
    ),
    (
        "list_templates",
        "templates",
        {"items": [TEMPLATE], "total_count": "1"},
        {},
        lambda parsed: (
            parsed.total == 1
            and parsed.has_more is False
            and parsed.items[0].metadata.id == "uuid-1"
            and parsed.items[0].settings.file_upload.enabled is False
        ),
    ),
    (
        "get_template",
        "templates/uuid-1",
        TEMPLATE,
        {"template_id": "uuid-1"},
        lambda parsed: parsed.metadata.status == "active" and parsed.settings.name == "Default",
    ),
]


@pytest.mark.parametrize(("method", "path", "body", "kwargs", "check"), CASES)
@respx.mock
def test_sync(method, path, body, kwargs, check):
    route = respx.get(f"https://test.goskope.com/api/v2/rbi/{path}").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        response = getattr(client.rbi.with_response, method)(**kwargs)
        parsed = response.parse()
        assert check(parsed)
        assert response.parse() is parsed
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize(("method", "path", "body", "kwargs", "check"), CASES)
@respx.mock
async def test_async(method, path, body, kwargs, check):
    route = respx.get(f"https://test.goskope.com/api/v2/rbi/{path}").respond(200, json=body)
    async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        response = await getattr(client.rbi.with_response, method)(**kwargs)
        assert check(response.parse())
        assert response.parse() is response.parse()
        assert response.json() == body
    assert route.call_count == 1


@pytest.mark.parametrize("template_id", ["1234", 1234])
@pytest.mark.parametrize("asynchronous", [False, True])
@respx.mock
async def test_numeric_template_id_matches_its_string_identity(asynchronous, template_id):
    body = {
        "template_metadata": {"template_id": template_id, "template_status": "active"},
        "template_data": {"name": "Numeric"},
    }
    route = respx.get("https://test.goskope.com/api/v2/rbi/templates/1234").respond(200, json=body)
    if asynchronous:
        async with AsyncNetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            response = await client.rbi.with_response.get_template(1234)
    else:
        with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
            response = client.rbi.with_response.get_template(1234)
    assert response.parse().settings.name == "Numeric"
    assert route.call_count == 1


@pytest.mark.parametrize(
    "body",
    [
        {"items": ["sensitive-invalid"]},
        {
            "items": [
                {
                    "template_metadata": {"template_id": "uuid-1"},
                    "template_data": {"file_upload": True},
                }
            ]
        },
    ],
)
@respx.mock
def test_invalid_pages(body):
    respx.get("https://test.goskope.com/api/v2/rbi/templates").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        response = client.rbi.with_response.list_templates()
        with pytest.raises(ResponseValidationError) as caught:
            response.parse()
        assert "sensitive-invalid" not in str(caught.value)
        assert response.json() == body


@pytest.mark.parametrize(
    "body",
    [
        {"items": [TEMPLATE], "total_count": 0},
        {"items": [TEMPLATE], "offset": 5},
    ],
)
@respx.mock
def test_pages_that_cannot_be_continued_safely(body):
    respx.get("https://test.goskope.com/api/v2/rbi/templates").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        response = client.rbi.with_response.list_templates()
        with pytest.raises(PaginationError) as caught:
            response.parse()
        assert caught.value.request_path == "/api/v2/rbi/templates"
        assert caught.value.offset == 0
        assert response.json() == body


@respx.mock
def test_unusable_total_states_no_total():
    body = {"items": [TEMPLATE], "total_count": False}
    respx.get("https://test.goskope.com/api/v2/rbi/templates").respond(200, json=body)
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        page = client.rbi.with_response.list_templates().parse()
    assert page.total is None
    assert page.has_more is None


@respx.mock
def test_identity_and_input_validation():
    route = respx.get("https://test.goskope.com/api/v2/rbi/templates/uuid-2").respond(
        200, json=TEMPLATE
    )
    with NetskopeClient(tenant="test.goskope.com", api_token="token") as client:
        with pytest.raises(ResponseValidationError):
            client.rbi.with_response.get_template("uuid-2").parse()
        with pytest.raises(ValidationError):
            client.rbi.with_response.list_templates(limit=-1)
    assert route.call_count == 1
