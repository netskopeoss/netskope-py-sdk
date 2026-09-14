"""Second-pass conformance fixes not covered by the earlier SPEC2 test files.

Every test names the contract file and line it is derived from, so the claim can
be re-checked against `production/endpoints` without re-running the review.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from netskope import NetskopeClient
from netskope.exceptions import NotFoundError, RateLimitError, ValidationError
from netskope.models.atp import AtpScanReport
from netskope.models.dspm import DspmFileSensitiveType

_TENANT = "example.goskope.com"
_BASE = f"https://{_TENANT}"


@pytest.fixture
def client() -> NetskopeClient:
    return NetskopeClient(tenant=_TENANT, api_token="v2-token")


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def test_atp_scan_report_decodes_the_in_progress_poll() -> None:
    """atp/atpsvc.yaml:409-419 reuses TssScanReportResponse for the 202.

    That schema lists `verdict` as required (:66-73), but the 202's own example
    omits it, and polling is the documented flow.
    """
    report = AtpScanReport.model_validate(
        {
            "jobid": "j1",
            "md5": "d41d8cd98f00b204e9800998ecf8427e",
            "requests_served": 1,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb924",
            "status": "InProgress",
        }
    )
    assert report.verdict is None
    assert report.status == "InProgress"


def test_dspm_data_tags_accepts_strings_and_integers() -> None:
    """dspm_external.yaml:7162 declares `dataTags` with untyped items.

    Every sibling tag list in the same file is `items: {type: string}`.
    """
    record = DspmFileSensitiveType.model_validate({"dataTags": ["pii", 7]})
    assert record.data_tags == ["pii", 7]


# ---------------------------------------------------------------------------
# error mapping
# ---------------------------------------------------------------------------


@respx.mock
def test_status_not_found_on_http_200_raises_not_found(client: NetskopeClient) -> None:
    """`not found` is a declared 200-level status value.

    npa_publishers.yaml:871-876 (status_enum, used by the publishers
    list/get/create/update operations), npa_apps_private.yaml:25-26,
    npa_private_tag.yaml:412, npa_generic.yaml:152-156.
    """
    respx.get(f"{_BASE}/api/v2/infrastructure/publishers/7").mock(
        return_value=httpx.Response(200, json={"status": "not found"})
    )
    with pytest.raises(NotFoundError) as excinfo:
        client.publishers.get(7)
    assert "not found" in str(excinfo.value).lower()


@respx.mock
def test_error_message_field_reaches_the_exception(client: NetskopeClient) -> None:
    """atp/atpsvc.yaml:3-9 reports the diagnosis as `error_message`."""
    respx.post(f"{_BASE}/api/v2/atp/tpaas/urlscan/submission/scan").mock(
        return_value=httpx.Response(400, json={"error_message": "bad url", "status": "Error"})
    )
    with pytest.raises(Exception) as excinfo:
        client.atp.scan_url("http://example.com/a")
    assert "bad url" in str(excinfo.value)


@respx.mock
def test_rate_limit_reads_retry_after_from_the_body(client: NetskopeClient) -> None:
    """atp/urlscan.yaml:22-32 declares retry_after in the 429 body, not a header."""
    respx.post(f"{_BASE}/api/v2/atp/tpaas/urlscan/submission/scan").mock(
        return_value=httpx.Response(
            429, json={"message": "quota exceeded", "status": "Error", "retry_after": 120}
        )
    )
    with pytest.raises(RateLimitError) as excinfo:
        client.atp.scan_url("http://example.com/a")
    assert excinfo.value.retry_after == 120.0


# ---------------------------------------------------------------------------
# requests
# ---------------------------------------------------------------------------


@respx.mock
def test_get_tunnel_reads_the_result_envelope(client: NetskopeClient) -> None:
    """steering/ipsec.yaml:305-317 keys the single-tunnel read under `result`.

    The create (:90-101) and patch (:3-14) responses use `data`; both must decode.
    """
    respx.get(f"{_BASE}/api/v2/steering/ipsec/tunnels/5").mock(
        return_value=httpx.Response(
            200, json={"result": [{"id": 5, "site": "NYC"}], "status": "success", "total": 1}
        )
    )
    assert client.steering.get_tunnel(5).site == "NYC"

    respx.get(f"{_BASE}/api/v2/steering/ipsec/tunnels/6").mock(
        return_value=httpx.Response(200, json={"data": {"id": 6, "site": "SFO"}})
    )
    assert client.steering.get_tunnel(6).site == "SFO"


@respx.mock
def test_spm_past_view_requires_a_timestamp(client: NetskopeClient) -> None:
    """spm/inventory.yaml:343-352 and :371-379 — past_view=true requires timestamp."""
    route = respx.post(f"{_BASE}/api/v2/spm/inventory/getresources").mock(
        return_value=httpx.Response(200, json={"data": {"results": [], "total": 0}})
    )
    with pytest.raises(ValidationError, match="timestamp"):
        client.spm.inventory(past_view=True)
    assert not route.calls

    client.spm.inventory(past_view=True, timestamp=1700000000)
    assert route.calls


@respx.mock
def test_rbi_list_templates_accepts_a_single_status(client: NetskopeClient) -> None:
    """rbi/templates.yaml:220-229 declares `status` as an array, style=form.

    A bare `str` is iterable, so forwarding it unchanged produced
    `status=a,p,p,l,i,e,d`.
    """
    route = respx.get(f"{_BASE}/api/v2/rbi/templates").mock(
        return_value=httpx.Response(200, json={"data": [], "total_count": 0})
    )
    client.rbi.list_templates(status="applied")
    assert dict(route.calls[-1].request.url.params)["status"] == "applied"

    client.rbi.list_templates(status=["applied", "pending-create"])
    assert dict(route.calls[-1].request.url.params)["status"] == "applied,pending-create"


@respx.mock
def test_rbi_deploy_bounds_its_template_ids(client: NetskopeClient) -> None:
    """rbi/templates.yaml:2061 and :2085 set minItems 1; :456-460 forbids all+ids."""
    route = respx.post(f"{_BASE}/api/v2/rbi/templates/deploy").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    client.rbi.deploy_templates("abc")
    assert route.calls[-1].request.read() == b'{"template_ids":["abc"]}'

    with pytest.raises(ValidationError, match="at least one template"):
        client.rbi.deploy_templates([])
    with pytest.raises(ValidationError, match="exactly one"):
        client.rbi.deploy_templates(["a"], deploy_all=True)
