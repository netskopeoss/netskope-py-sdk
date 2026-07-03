"""Tests for the NSIQ (Netskope Intelligence) resource with mocked HTTP.

Pins the wire contract of the ``/api/v2/nsiq`` surface against the
api-gateway OpenAPI specs: URL lookup wraps URLs in ``{"query": {"urls":
[...]}}`` (single strings are normalized to a one-element list),
re-categorization posts ``{"email", "recat_requests": [...]}``, RetroHunt IOC
lookups post ``{"hash": [...]}``, and false-positive submissions post
``{"user_email", "fp_data": [{"incident_id", ...}]}``.

``client.nsiq`` is intentionally not wired onto the client yet, so these tests
instantiate the resource classes directly against the client's transport.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.resources.nsiq import AsyncNsiqResource, NsiqResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/nsiq"
_URLLOOKUP_URL = f"{_BASE}/urllookup"
_RECAT_URL = f"{_BASE}/url/recategorizations"
_GETINFO_URL = f"{_BASE}/retrohunt/ioc/getinfo"
_INFO_URL = f"{_BASE}/retrohunt/ioc/info"
_REPORT_URL = f"{_BASE}/retrohunt/ioc/report"
_FP_URL_URL = f"{_BASE}/falsepositives/url"
_FP_MALWARE_URL = f"{_BASE}/falsepositives/malware"
_FP_IPS_URL = f"{_BASE}/falsepositives/ips"
_FP_VALIDATE_URL = f"{_BASE}/falsepositives/validations/useremail"

_OK = {"status": "OK"}


def _nsiq(client: NetskopeClient) -> NsiqResource:
    return NsiqResource(client._transport)


def _ansiq(aclient: AsyncNetskopeClient) -> AsyncNsiqResource:
    return AsyncNsiqResource(aclient._transport)


class TestUrlLookup:
    @respx.mock
    def test_single_url_is_wrapped_in_list(self, client: NetskopeClient) -> None:
        route = respx.post(_URLLOOKUP_URL).mock(
            return_value=httpx.Response(200, json={"result": []})
        )
        result = _nsiq(client).url_lookup("https://www.google.com")

        assert result == {"result": []}
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"query": {"urls": ["https://www.google.com"]}}

    @respx.mock
    def test_list_of_urls_passed_through(self, client: NetskopeClient) -> None:
        route = respx.post(_URLLOOKUP_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).url_lookup(["https://a.com", "https://b.com"])

        assert sent_json(route) == {"query": {"urls": ["https://a.com", "https://b.com"]}}

    @respx.mock
    def test_optional_query_flags(self, client: NetskopeClient) -> None:
        route = respx.post(_URLLOOKUP_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).url_lookup("a.com", disable_dns_lookup=True, category="swg")

        assert sent_json(route) == {
            "query": {"urls": ["a.com"], "disable_dns_lookup": True, "category": "swg"}
        }

    @respx.mock
    async def test_async_single_url(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_URLLOOKUP_URL).mock(return_value=httpx.Response(200, json=_OK))
        result = await _ansiq(aclient).url_lookup("https://www.google.com")

        assert result == _OK
        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"query": {"urls": ["https://www.google.com"]}}


class TestRecategorize:
    @respx.mock
    def test_body_shape_minimal(self, client: NetskopeClient) -> None:
        route = respx.post(_RECAT_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).recategorize("example.com", ["Technology", "Business"])

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {
            "email": "",
            "recat_requests": [
                {"url": "example.com", "suggested_categories": ["Technology", "Business"]}
            ],
        }

    @respx.mock
    def test_body_shape_with_justification_and_email(self, client: NetskopeClient) -> None:
        route = respx.post(_RECAT_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).recategorize(
            "example.com",
            ["Technology"],
            justification="dev docs",
            email="me@example.com",
        )

        assert sent_json(route) == {
            "email": "me@example.com",
            "recat_requests": [{"url": "example.com", "suggested_categories": ["Technology"]}],
            "justification": "dev docs",
        }

    @respx.mock
    async def test_async_body_shape(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_RECAT_URL).mock(return_value=httpx.Response(201, json=_OK))
        await _ansiq(aclient).recategorize("example.com", ["Technology"])

        assert sent_json(route) == {
            "email": "",
            "recat_requests": [{"url": "example.com", "suggested_categories": ["Technology"]}],
        }


class TestRecategorizationStatus:
    @respx.mock
    def test_list_default_params(self, client: NetskopeClient) -> None:
        route = respx.get(_RECAT_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).list_recategorizations()

        assert route.calls.last.request.method == "GET"
        assert dict(route.calls.last.request.url.params) == {
            "offset": "0",
            "limit": "5",
            "sortby": "task_id",
            "sortorder": "asc",
        }

    @respx.mock
    def test_list_with_filters(self, client: NetskopeClient) -> None:
        route = respx.get(_RECAT_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).list_recategorizations(
            start_time=1000, end_time=2000, status="completed", limit=10, sort_order="desc"
        )

        params = dict(route.calls.last.request.url.params)
        assert params["starttime"] == "1000"
        assert params["endtime"] == "2000"
        assert params["status"] == "completed"
        assert params["limit"] == "10"
        assert params["sortorder"] == "desc"

    @respx.mock
    def test_get_by_task_id(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_RECAT_URL}/100").mock(return_value=httpx.Response(200, json=_OK))
        result = _nsiq(client).get_recategorization("100")

        assert result == _OK
        assert route.calls.last.request.method == "GET"

    @respx.mock
    def test_get_url_status(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_RECAT_URL}/100/urls/12345").mock(
            return_value=httpx.Response(200, json=_OK)
        )
        _nsiq(client).get_recategorization_url_status("100", "12345")

        assert route.calls.last.request.method == "GET"

    @respx.mock
    async def test_async_get_by_task_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_RECAT_URL}/100").mock(return_value=httpx.Response(200, json=_OK))
        await _ansiq(aclient).get_recategorization("100")

        assert route.calls.last.request.method == "GET"


class TestRetrohunt:
    @respx.mock
    def test_lookup_iocs_single_hash_wrapped(self, client: NetskopeClient) -> None:
        route = respx.post(_GETINFO_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).lookup_iocs("abc123")

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {"hash": ["abc123"]}

    @respx.mock
    def test_lookup_iocs_list(self, client: NetskopeClient) -> None:
        route = respx.post(_GETINFO_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).lookup_iocs(["abc123", "def456"])

        assert sent_json(route) == {"hash": ["abc123", "def456"]}

    @respx.mock
    def test_get_ioc_sends_hash_param(self, client: NetskopeClient) -> None:
        route = respx.get(_INFO_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).get_ioc("abc123")

        assert route.calls.last.request.method == "GET"
        assert dict(route.calls.last.request.url.params) == {"hash": "abc123"}

    @respx.mock
    def test_get_ioc_report_sends_hash_param(self, client: NetskopeClient) -> None:
        route = respx.get(_REPORT_URL).mock(return_value=httpx.Response(200, json=_OK))
        _nsiq(client).get_ioc_report("abc123")

        assert dict(route.calls.last.request.url.params) == {"hash": "abc123"}

    @respx.mock
    async def test_async_lookup_iocs(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_GETINFO_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _ansiq(aclient).lookup_iocs("abc123")

        assert sent_json(route) == {"hash": ["abc123"]}

    @respx.mock
    async def test_async_get_ioc(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(_INFO_URL).mock(return_value=httpx.Response(200, json=_OK))
        await _ansiq(aclient).get_ioc("abc123")

        assert dict(route.calls.last.request.url.params) == {"hash": "abc123"}


class TestFalsePositives:
    @respx.mock
    def test_report_url_fp_minimal(self, client: NetskopeClient) -> None:
        route = respx.post(_FP_URL_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).report_url_false_positive("1234512345", "user@example.com")

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {
            "user_email": "user@example.com",
            "fp_data": [{"incident_id": "1234512345"}],
        }

    @respx.mock
    def test_report_url_fp_full(self, client: NetskopeClient) -> None:
        route = respx.post(_FP_URL_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).report_url_false_positive(
            "1234512345",
            "user@example.com",
            url="http://example.com/",
            page="http://example.com/?q=1",
            description="url fp test",
            current_category_id=[521, 588],
            tenant_user_name="Tester",
        )

        assert sent_json(route) == {
            "user_email": "user@example.com",
            "fp_data": [
                {
                    "incident_id": "1234512345",
                    "url": "http://example.com/",
                    "page": "http://example.com/?q=1",
                    "description": "url fp test",
                    "current_category_id": [521, 588],
                }
            ],
            "tenant_user_name": "Tester",
        }

    @respx.mock
    def test_report_malware_fp(self, client: NetskopeClient) -> None:
        route = respx.post(_FP_MALWARE_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).report_malware_false_positive(
            "1234512345", "user@example.com", md5="e92399ce76e82a536ab47203a54ee1f2", mode="inline"
        )

        assert sent_json(route) == {
            "user_email": "user@example.com",
            "fp_data": [
                {
                    "incident_id": "1234512345",
                    "md5": "e92399ce76e82a536ab47203a54ee1f2",
                    "mode": "inline",
                }
            ],
        }

    @respx.mock
    def test_report_ips_fp(self, client: NetskopeClient) -> None:
        route = respx.post(_FP_IPS_URL).mock(return_value=httpx.Response(201, json=_OK))
        _nsiq(client).report_ips_false_positive(
            "1234512345", "user@example.com", signature_id="12345", url="http://example.com/"
        )

        assert sent_json(route) == {
            "user_email": "user@example.com",
            "fp_data": [
                {
                    "incident_id": "1234512345",
                    "url": "http://example.com/",
                    "signature_id": "12345",
                }
            ],
        }

    @respx.mock
    def test_validate_user_email(self, client: NetskopeClient) -> None:
        route = respx.post(_FP_VALIDATE_URL).mock(
            return_value=httpx.Response(200, json={"is_valid": True, "user_email": "u@x.com"})
        )
        result = _nsiq(client).validate_user_email("u@x.com")

        assert result == {"is_valid": True, "user_email": "u@x.com"}
        assert sent_json(route) == {"user_email": "u@x.com"}

    @respx.mock
    async def test_async_report_url_fp(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_FP_URL_URL).mock(return_value=httpx.Response(201, json=_OK))
        await _ansiq(aclient).report_url_false_positive("1234512345", "user@example.com")

        assert route.calls.last.request.method == "POST"
        assert sent_json(route) == {
            "user_email": "user@example.com",
            "fp_data": [{"incident_id": "1234512345"}],
        }

    @respx.mock
    async def test_async_validate_user_email(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(_FP_VALIDATE_URL).mock(
            return_value=httpx.Response(200, json={"is_valid": False, "user_email": "u@x.com"})
        )
        await _ansiq(aclient).validate_user_email("u@x.com")

        assert sent_json(route) == {"user_email": "u@x.com"}


@pytest.mark.parametrize("verb", ["url", "malware", "ips"])
def test_fp_paths_exist(verb: str) -> None:
    """Guard against typos in the false-positive path constants."""
    from netskope.resources import nsiq

    path = getattr(nsiq, f"_FP_{verb.upper()}_PATH")
    assert path == f"/api/v2/nsiq/falsepositives/{verb}"
