"""Tests for the ATP (Advanced Threat Protection) resource with mocked HTTP.

``client.atp`` is intentionally not wired onto the client, so these tests
drive the resource classes directly via ``AtpResource(client._transport)`` and
``AsyncAtpResource(aclient._transport)``.
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient
from netskope.exceptions import ValidationError
from netskope.resources.atp.resource import AsyncAtpResource, AtpResource
from tests.unit.resources.conftest import sent_json

_BASE = "https://t.goskope.com/api/v2/atp"

# A benign text member named sample.exe, ZipCrypto-encrypted with password
# infected — the only upload shape POST /scans/filescan accepts
# (atp/atpsvc.yaml:86-105).
_ARCHIVE = base64.b64decode(
    "UEsDBAoACQAAAMNyKV0dmP5SNAAAACgAAAAKABwAc2FtcGxlLmV4ZVVUCQADzqOhas6joWp1eAsA"
    "AQT1AQAABAAAAAAYutMo+qaQL8/kSDAG8FcXL8iBw+jUOO6NowntO5VRFfREeUS7Y6jU885JKAWc"
    "akk+hhsVUEsHCB2Y/lI0AAAAKAAAAFBLAQIeAwoACQAAAMNyKV0dmP5SNAAAACgAAAAKABgAAAAA"
    "AAEAAACkgQAAAABzYW1wbGUuZXhlVVQFAAPOo6FqdXgLAAEE9QEAAAQAAAAAUEsFBgAAAAABAAEA"
    "UAAAAIgAAAAAAA=="
)


class TestAtpResourceSync:
    """Sync ATP resource: URL, verb, and payload per method."""

    @respx.mock
    def test_scan_file_multipart_and_scantype_query(self, client: NetskopeClient) -> None:
        """The upload is multipart with a required ``scantype`` query (atpsvc.yaml:94-105)."""
        route = respx.post(f"{_BASE}/scans/filescan").mock(
            return_value=httpx.Response(200, json={"jobid": "abc123", "status": "Ok"})
        )
        atp = AtpResource(client._transport)
        result = atp.scan_file("sample.zip", _ARCHIVE)

        assert route.called
        request = route.calls.last.request
        assert dict(request.url.params) == {"scantype": "sandbox"}
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        assert b'name="file"; filename="sample.zip"' in request.content
        assert _ARCHIVE in request.content
        assert base64.b64encode(_ARCHIVE) not in request.content
        assert result["jobid"] == "abc123"

    @respx.mock
    def test_scan_file_rejects_an_unsupported_scan_type(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        atp = AtpResource(client._transport)
        with pytest.raises(ValidationError, match="sandbox"):
            atp.scan_file("sample.zip", _ARCHIVE, scan_type="realtime")
        assert route.call_count == 0

    @respx.mock
    def test_scan_file_rejects_a_plain_file(self, client: NetskopeClient) -> None:
        route = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
        atp = AtpResource(client._transport)
        with pytest.raises(ValidationError, match="encrypted ZIP archive"):
            atp.scan_file("evil.exe", b"hello world")
        assert route.call_count == 0

    @respx.mock
    def test_scan_file_path_reads_bytes(self, client: NetskopeClient, tmp_path) -> None:
        f = tmp_path / "sample.zip"
        f.write_bytes(_ARCHIVE)
        route = respx.post(f"{_BASE}/scans/filescan").mock(
            return_value=httpx.Response(200, json={"jobid": "j"})
        )
        atp = AtpResource(client._transport)
        atp.scan_file_path(f)

        request = route.calls.last.request
        assert dict(request.url.params) == {"scantype": "sandbox"}
        assert b'name="file"; filename="sample.zip"' in request.content

    @respx.mock
    def test_get_report_quotes_id(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE}/scans/reports/job%2F123").mock(
            return_value=httpx.Response(200, json={"verdict": "malicious"})
        )
        atp = AtpResource(client._transport)
        result = atp.get_report("job/123")

        assert route.called
        assert result["verdict"] == "malicious"

    @respx.mock
    def test_scan_url_flat_body(self, client: NetskopeClient) -> None:
        route = respx.post(f"{_BASE}/tpaas/urlscan/submission/scan").mock(
            return_value=httpx.Response(202, json={"submission_id": "s1", "status": "Ok"})
        )
        atp = AtpResource(client._transport)
        result = atp.scan_url("https://bad.example.com/x")

        assert route.called
        assert sent_json(route) == {"url": "https://bad.example.com/x"}
        assert result["submission_id"] == "s1"

    @respx.mock
    def test_get_submission_report_quotes_id(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/submission/sub%2Fid/reports").mock(
            return_value=httpx.Response(200, json={"report": {}})
        )
        atp = AtpResource(client._transport)
        result = atp.get_submission_report("sub/id")

        assert route.called
        assert "report" in result

    @respx.mock
    def test_get_scan_result(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/submission/s1/result").mock(
            return_value=httpx.Response(200, json={"verdict": "malicious"})
        )
        atp = AtpResource(client._transport)
        result = atp.get_scan_result("s1")

        assert route.called
        assert result["verdict"] == "malicious"

    @respx.mock
    def test_get_url_report(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/urlscan/s1/report").mock(
            return_value=httpx.Response(200, json={"verdict": "non-malicious"})
        )
        atp = AtpResource(client._transport)
        result = atp.get_url_report("s1")

        assert route.called
        assert result["verdict"] == "non-malicious"

    @respx.mock
    def test_list_url_artifacts(self, client: NetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/urlscan/s1/artifacts").mock(
            return_value=httpx.Response(200, json={"artifact_count": 0, "artifacts": []})
        )
        atp = AtpResource(client._transport)
        result = atp.list_url_artifacts("s1")

        assert route.called
        assert result["artifact_count"] == 0

    def test_get_report_rejects_bad_id(self, client: NetskopeClient) -> None:
        atp = AtpResource(client._transport)
        with pytest.raises(ValidationError):
            atp.get_report("bad id")  # whitespace is rejected by quote_id


class TestAtpResourceAsync:
    """Async ATP resource mirrors the sync surface."""

    @respx.mock
    async def test_scan_file_multipart_and_scantype_query(
        self, aclient: AsyncNetskopeClient
    ) -> None:
        route = respx.post(f"{_BASE}/scans/filescan").mock(
            return_value=httpx.Response(200, json={"jobid": "abc123"})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.scan_file("sample.zip", _ARCHIVE)

        request = route.calls.last.request
        assert dict(request.url.params) == {"scantype": "sandbox"}
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        assert _ARCHIVE in request.content
        assert result["jobid"] == "abc123"

    @respx.mock
    async def test_scan_file_path_reads_bytes(self, aclient: AsyncNetskopeClient, tmp_path) -> None:
        f = tmp_path / "sample.zip"
        f.write_bytes(_ARCHIVE)
        route = respx.post(f"{_BASE}/scans/filescan").mock(
            return_value=httpx.Response(200, json={"jobid": "j"})
        )
        atp = AsyncAtpResource(aclient._transport)
        await atp.scan_file_path(f)

        assert b'name="file"; filename="sample.zip"' in route.calls.last.request.content

    @respx.mock
    async def test_get_report_quotes_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/scans/reports/job%2F123").mock(
            return_value=httpx.Response(200, json={"verdict": "malicious"})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.get_report("job/123")

        assert route.called
        assert result["verdict"] == "malicious"

    @respx.mock
    async def test_scan_url_flat_body(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.post(f"{_BASE}/tpaas/urlscan/submission/scan").mock(
            return_value=httpx.Response(202, json={"submission_id": "s1"})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.scan_url("https://bad.example.com/x")

        assert sent_json(route) == {"url": "https://bad.example.com/x"}
        assert result["submission_id"] == "s1"

    @respx.mock
    async def test_get_submission_report_quotes_id(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/submission/sub%2Fid/reports").mock(
            return_value=httpx.Response(200, json={"report": {}})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.get_submission_report("sub/id")

        assert route.called
        assert "report" in result

    @respx.mock
    async def test_get_scan_result(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/submission/s1/result").mock(
            return_value=httpx.Response(200, json={"verdict": "malicious"})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.get_scan_result("s1")

        assert route.called
        assert result["verdict"] == "malicious"

    @respx.mock
    async def test_get_url_report(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/urlscan/s1/report").mock(
            return_value=httpx.Response(200, json={"verdict": "unknown"})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.get_url_report("s1")

        assert route.called
        assert result["verdict"] == "unknown"

    @respx.mock
    async def test_list_url_artifacts(self, aclient: AsyncNetskopeClient) -> None:
        route = respx.get(f"{_BASE}/tpaas/urlscan/s1/artifacts").mock(
            return_value=httpx.Response(200, json={"artifact_count": 2})
        )
        atp = AsyncAtpResource(aclient._transport)
        result = await atp.list_url_artifacts("s1")

        assert route.called
        assert result["artifact_count"] == 2
