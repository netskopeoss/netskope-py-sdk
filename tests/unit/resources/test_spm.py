"""Tests for the SPM (SaaS Security Posture Management) resource with mocked HTTP.

Pins the wire shapes for the SPM public API surface: ``list_apps``/``get_app``
under ``/api/v2/spm/apps`` (app names are percent-encoded, so a space becomes
``%20``), ``inventory`` POSTs a ``{"filter": <str>}`` body (or none),
``posture_score`` reads ``/saas_posture_score``, ``list_policy_rules`` reads
``/policy/rules``, and ``recent_changes`` reads ``/apps/recentchanges/getstats``.
All methods return the raw response body verbatim.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.resources.spm import AsyncSpmResource, SpmResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/spm"
_APPS_URL = f"{_BASE}/apps"
_INVENTORY_URL = f"{_BASE}/inventory"
_POSTURE_URL = f"{_BASE}/saas_posture_score"
_RULES_URL = f"{_BASE}/policy/rules"
_RECENT_URL = f"{_BASE}/apps/recentchanges/getstats"


def _spm(client: NetskopeClient) -> SpmResource:
    return SpmResource(client._transport)


def _aspm(aclient: AsyncNetskopeClient) -> AsyncSpmResource:
    return AsyncSpmResource(aclient._transport)


class TestListApps:
    """Tests for SpmResource.list_apps."""

    @respx.mock
    def test_list_apps(self, client: NetskopeClient) -> None:
        body = {"data": [{"name": "Microsoft 365", "posture_score": 75}]}
        route = respx.get(_APPS_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).list_apps()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_apps_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": [{"name": "Salesforce"}]}
        route = respx.get(_APPS_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).list_apps()

        assert result == body
        assert route.calls.last.request.method == "GET"


class TestGetApp:
    """Tests for SpmResource.get_app — app names may contain spaces."""

    @respx.mock
    def test_get_app_encodes_space(self, client: NetskopeClient) -> None:
        encoded_url = f"{_APPS_URL}/Microsoft%20365"
        body = {"data": {"name": "Microsoft 365", "posture_score": 75}}
        route = respx.get(encoded_url).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).get_app("Microsoft 365")

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        # The space must be percent-encoded (%20) in the raw request path,
        # never sent literally or as a "+".
        assert "%20" in request.url.raw_path.decode()
        assert request.url.raw_path.decode().endswith("/Microsoft%20365")

    @respx.mock
    async def test_get_app_encodes_space_async(self, aclient: AsyncNetskopeClient) -> None:
        encoded_url = f"{_APPS_URL}/Microsoft%20365"
        body = {"data": {"name": "Microsoft 365"}}
        route = respx.get(encoded_url).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).get_app("Microsoft 365")

        assert result == body
        assert "%20" in route.calls.last.request.url.raw_path.decode()


class TestInventory:
    """Tests for SpmResource.inventory — POST with optional filter body."""

    @respx.mock
    def test_inventory_no_filter_sends_no_body(self, client: NetskopeClient) -> None:
        body = {"data": []}
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).inventory()

        assert result == body
        request = route.calls.last.request
        assert request.method == "POST"
        # No filter -> empty request body.
        assert request.content == b""

    @respx.mock
    def test_inventory_with_filter_sends_filter_body(self, client: NetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        _spm(client).inventory(filter='{"app_name": "Slack"}')

        assert sent_json(route) == {"filter": '{"app_name": "Slack"}'}

    @respx.mock
    async def test_inventory_with_filter_body_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        await _aspm(aclient).inventory(filter="app:Slack")

        assert sent_json(route) == {"filter": "app:Slack"}
        assert route.calls.last.request.method == "POST"


class TestPostureScore:
    """Tests for SpmResource.posture_score."""

    @respx.mock
    def test_posture_score(self, client: NetskopeClient) -> None:
        body = {"data": {"posture_score": 82}}
        route = respx.get(_POSTURE_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).posture_score()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_posture_score_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": {"posture_score": 82}}
        route = respx.get(_POSTURE_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).posture_score()

        assert result == body
        assert route.calls.last.request.method == "GET"


class TestListPolicyRules:
    """Tests for SpmResource.list_policy_rules."""

    @respx.mock
    def test_list_policy_rules(self, client: NetskopeClient) -> None:
        body = {"data": [{"name": "Enforce MFA", "severity": "High"}]}
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).list_policy_rules()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_list_policy_rules_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": [{"name": "Enforce MFA"}]}
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).list_policy_rules()

        assert result == body
        assert route.calls.last.request.method == "GET"


class TestRecentChanges:
    """Tests for SpmResource.recent_changes."""

    @respx.mock
    def test_recent_changes(self, client: NetskopeClient) -> None:
        body = {"trends": {"samples": []}}
        route = respx.get(_RECENT_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).recent_changes()

        assert result == body
        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_recent_changes_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"trends": {"samples": []}}
        route = respx.get(_RECENT_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).recent_changes()

        assert result == body
        assert route.calls.last.request.method == "GET"


@pytest.mark.parametrize(
    ("name", "expected_suffix"),
    [
        ("Salesforce", "/apps/Salesforce"),
        ("Microsoft 365", "/apps/Microsoft%20365"),
        ("A/B App", "/apps/A%2FB%20App"),
    ],
)
def test_app_path_encoding(name: str, expected_suffix: str) -> None:
    """A slash must be encoded so it cannot alter the request path."""
    from netskope.resources.spm import _app_path

    assert _app_path(name).endswith(expected_suffix)
