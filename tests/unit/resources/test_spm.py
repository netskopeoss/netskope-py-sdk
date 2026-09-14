"""Tests for the SPM (SaaS Security Posture Management) resource with mocked HTTP.

Pins the wire shapes against ``production/endpoints/spm``:

* ``POST /inventory/getresources`` (inventory.yaml:1035) with the four required
  ``ResourceAggregationRequest`` fields ``fields``/``group_by``/``limit``/
  ``offset`` (:380-385), and ``filters`` as ``{column: {operator, values}}``
  (:300-321) — this is the only ``/inventory`` operation the service declares.
* ``POST /results/getposturescores`` (saas_posture_score.yaml:227) with the
  optional ``GetPostureScoresRequestBody`` (:26-46).
* ``GET /rules/list`` (policy.yaml:2833) with its declared query parameters.
* ``POST /apps/recentchanges/getstats`` (apps.yaml:1722) with the required
  ``RecentChangesRequest.time_range`` (:616-649).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources.spm.resource import AsyncSpmResource, SpmResource
from tests.unit.resources.conftest import EXAMPLE_BASE, sent_json

_BASE = "https://t.goskope.com/api/v2/spm"
_INVENTORY_URL = f"{_BASE}/inventory/getresources"
_POSTURE_URL = f"{_BASE}/results/getposturescores"
_RULES_URL = f"{_BASE}/rules/list"
_RECENT_URL = f"{_BASE}/apps/recentchanges/getstats"


def _spm(client: NetskopeClient) -> SpmResource:
    return SpmResource(client._transport)


def _aspm(aclient: AsyncNetskopeClient) -> AsyncSpmResource:
    return AsyncSpmResource(aclient._transport)


class TestListApps:
    """``list_apps`` aggregates the inventory by SaaS instance."""

    @respx.mock
    def test_list_apps_posts_an_instance_aggregation(self, client: NetskopeClient) -> None:
        body = {"data": [{"instance_name": "m365", "app_suite": "Microsoft365"}], "total_count": 1}
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).list_apps(limit=25, offset=50)

        assert result == body
        assert route.calls.last.request.method == "POST"
        sent = sent_json(route)
        assert sent["group_by"] == "instance_name"
        assert sent["limit"] == 25
        assert sent["offset"] == 50
        assert sent["fields"][:2] == ["instance_name", "app_suite"]
        assert "filters" not in sent

    @respx.mock
    async def test_list_apps_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"data": [{"instance_name": "salesforce"}]}
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).list_apps()

        assert result == body
        assert sent_json(route)["group_by"] == "instance_name"


class TestGetApp:
    """``get_app`` filters the inventory to one application."""

    @respx.mock
    def test_get_app_sends_an_equal_filter(self, client: NetskopeClient) -> None:
        body = {"data": [{"resource_type": "Policies", "app_name": "Microsoft 365"}]}
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).get_app("Microsoft 365")

        assert result == body
        sent = sent_json(route)
        assert sent["filters"] == {"app_name": {"operator": "equal", "values": ["Microsoft 365"]}}
        assert sent["group_by"] == "resource_type"
        assert "app_name" in sent["fields"]

    @respx.mock
    def test_get_app_rejects_a_blank_name_without_http(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="app_name"):
            _spm(client).get_app("   ")
        assert route.call_count == 0

    @respx.mock
    async def test_get_app_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        await _aspm(aclient).get_app("Salesforce")

        assert sent_json(route)["filters"]["app_name"]["values"] == ["Salesforce"]


class TestInventory:
    """``inventory`` always sends the four required aggregation fields."""

    @respx.mock
    def test_inventory_sends_the_required_fields(self, client: NetskopeClient) -> None:
        body = {"data": [], "next_offset": -1}
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).inventory()

        assert result == body
        sent = sent_json(route)
        assert set(sent) == {"fields", "group_by", "limit", "offset"}
        assert sent["group_by"] == "resource_name"
        assert sent["limit"] == 50
        assert sent["offset"] == 0
        assert "resource_name" in sent["fields"]

    @respx.mock
    def test_inventory_filter_alias_becomes_ngl_query(self, client: NetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        _spm(client).inventory(filter="app_name = 'Slack'")

        assert sent_json(route)["ngl_query"] == "app_name = 'Slack'"

    @respx.mock
    def test_inventory_sends_column_filters(self, client: NetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        _spm(client).inventory(
            group_by="resource_type",
            fields=["resource_type", "app_suite"],
            filters={"app_suite": {"operator": "equal", "values": ["AzureAD", "Microsoft365"]}},
            sort=[{"column": "resource_type", "sort_order": "desc"}],
            timestamp=1703894400,
            past_view=True,
        )

        sent = sent_json(route)
        assert sent["fields"] == ["resource_type", "app_suite"]
        assert sent["filters"]["app_suite"]["values"] == ["AzureAD", "Microsoft365"]
        assert sent["sort"] == [{"column": "resource_type", "sort_order": "desc"}]
        assert sent["timestamp"] == 1703894400
        assert sent["past_view"] is True

    @respx.mock
    def test_filters_and_ngl_query_are_exclusive(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="mutually exclusive"):
            _spm(client).inventory(filters={"app_name": {}}, ngl_query="x")
        assert route.call_count == 0

    @respx.mock
    def test_ngl_query_and_its_deprecated_alias_are_exclusive(self, client: NetskopeClient) -> None:
        """Preferring the alias would send the deprecated value and drop the current one."""
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="not both"):
            _spm(client).inventory(filter="deprecated", ngl_query="current")
        assert route.call_count == 0

    @respx.mock
    def test_ngl_query_requires_resource_name_grouping(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="resource_name"):
            _spm(client).inventory(ngl_query="x", group_by="instance_name")
        assert route.call_count == 0

    @respx.mock
    def test_unknown_group_by_is_rejected(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="Invalid group_by"):
            _spm(client).inventory(group_by="app_suite")
        assert route.call_count == 0

    @respx.mock
    async def test_inventory_async(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_INVENTORY_URL).mock(return_value=httpx.Response(200, json={"data": []}))

        await _aspm(aclient).inventory(filter="app:Slack")

        assert sent_json(route)["ngl_query"] == "app:Slack"
        assert route.calls.last.request.method == "POST"


class TestPostureScore:
    """``posture_score`` POSTs an optional filter body."""

    @respx.mock
    def test_posture_score_without_filters(self, client: NetskopeClient) -> None:
        body = {"score": {"posture_confidence_index": 82}}
        route = respx.post(_POSTURE_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).posture_score()

        assert result == body
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {}

    @respx.mock
    def test_posture_score_with_filters(self, client: NetskopeClient) -> None:
        route = respx.post(_POSTURE_URL).mock(return_value=httpx.Response(200, json={}))

        _spm(client).posture_score(
            app_names=["Defender"],
            appsuite_names=["Microsoft365"],
            instance_names=["microsoft365_account_id"],
            posture_confidence_level=["Medium"],
            timestamp=1696924810,
        )

        assert sent_json(route) == {
            "filters": {
                "app_names": ["Defender"],
                "appsuite_names": ["Microsoft365"],
                "instance_names": ["microsoft365_account_id"],
                "posture_confidence_level": ["Medium"],
            },
            "timestamp": 1696924810,
        }

    @respx.mock
    async def test_posture_score_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"score": {"posture_risk_score": 40}}
        route = respx.post(_POSTURE_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).posture_score(app_names=["Defender"])

        assert result == body
        assert sent_json(route)["filters"] == {"app_names": ["Defender"]}


class TestListPolicyRules:
    """``list_policy_rules`` reads ``GET /rules/list``."""

    @respx.mock
    def test_list_policy_rules_no_params(self, client: NetskopeClient) -> None:
        body = {"rules": [{"id": "1", "name": "Enforce MFA"}], "next_offset": 0}
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).list_policy_rules()

        assert result == body
        request = route.calls.last.request
        assert request.method == "GET"
        assert dict(request.url.params) == {}

    @respx.mock
    def test_list_policy_rules_sends_declared_query(self, client: NetskopeClient) -> None:
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json={"rules": []}))

        _spm(client).list_policy_rules(
            appsuite="AzureAD",
            filter="mfa",
            limit=200,
            view="latest",
            sort_order="desc",
            include_templates=True,
            offset=100,
        )

        assert dict(route.calls.last.request.url.params) == {
            "appsuite": "AzureAD",
            "filter": "mfa",
            "limit": "200",
            "view": "latest",
            "sortorder": "desc",
            "include_templates": "true",
            "offset": "100",
        }

    @respx.mock
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"view": "draft"}, "view must be one of"),
            ({"sort_order": "down"}, "sort_order must be one of"),
            ({"limit": 5000}, "must not exceed 1000"),
        ],
    )
    def test_rejected_query_values(
        self, client: NetskopeClient, kwargs: dict[str, object], message: str
    ) -> None:
        route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match=message):
            _spm(client).list_policy_rules(**kwargs)  # type: ignore[arg-type]
        assert route.call_count == 0

    @respx.mock
    def test_limit_minus_one_returns_every_rule(self, client: NetskopeClient) -> None:
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json={"rules": []}))
        _spm(client).list_policy_rules(limit=-1)
        assert dict(route.calls.last.request.url.params) == {"limit": "-1"}

    @respx.mock
    async def test_list_policy_rules_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"rules": [{"name": "Enforce MFA"}]}
        route = respx.get(_RULES_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).list_policy_rules(appsuite="AzureAD")

        assert result == body
        assert dict(route.calls.last.request.url.params) == {"appsuite": "AzureAD"}


class TestRecentChanges:
    """``recent_changes`` POSTs the required ``time_range``."""

    @respx.mock
    def test_recent_changes_sends_time_range(self, client: NetskopeClient) -> None:
        body = {"trends": {"samples": []}}
        route = respx.post(_RECENT_URL).mock(return_value=httpx.Response(200, json=body))

        result = _spm(client).recent_changes(start=1758127874, end=1759127874)

        assert result == body
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"time_range": {"start": 1758127874, "end": 1759127874}}

    @respx.mock
    def test_recent_changes_converts_datetimes_and_sends_filters(
        self, client: NetskopeClient
    ) -> None:
        route = respx.post(_RECENT_URL).mock(return_value=httpx.Response(200, json={}))

        _spm(client).recent_changes(
            start=datetime(2025, 9, 17, 16, 51, 14, tzinfo=UTC),
            end=datetime(2025, 9, 29, 6, 37, 54, tzinfo=UTC),
            app_name="GoogleWorkspace",
            instance_name="trireme-qe.com",
        )

        assert sent_json(route) == {
            "time_range": {"start": 1758127874, "end": 1759127874},
            "filters": {"app_name": "GoogleWorkspace", "instance_name": "trireme-qe.com"},
        }

    @respx.mock
    def test_missing_window_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="requires a time range"):
            _spm(client).recent_changes()
        assert route.call_count == 0

    @respx.mock
    def test_inverted_window_raises_without_http(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ValidationError, match="must not precede"):
            _spm(client).recent_changes(start=2, end=1)
        assert route.call_count == 0

    @respx.mock
    async def test_recent_changes_async(self, aclient: AsyncNetskopeClient) -> None:
        body = {"trends": {"samples": []}}
        route = respx.post(_RECENT_URL).mock(return_value=httpx.Response(200, json=body))

        result = await _aspm(aclient).recent_changes(start=1, end=2)

        assert result == body
        assert sent_json(route) == {"time_range": {"start": 1, "end": 2}}


# --- Gateway contract conformance -------------------------------------------------------------
#
# Folded in from the spec-conformance reviews: each test cites the
# production/endpoints file and line whose shape it pins.


@respx.mock
def test_spm_past_view_requires_a_timestamp(example_client: NetskopeClient) -> None:
    """spm/inventory.yaml:343-352 and :371-379 — past_view=true requires timestamp."""
    route = respx.post(f"{EXAMPLE_BASE}/api/v2/spm/inventory/getresources").mock(
        return_value=httpx.Response(200, json={"data": {"results": [], "total": 0}})
    )
    with pytest.raises(ValidationError, match="timestamp"):
        example_client.spm.inventory(past_view=True)
    assert not route.calls

    example_client.spm.inventory(past_view=True, timestamp=1700000000)
    assert route.calls
