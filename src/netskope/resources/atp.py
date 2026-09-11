"""Advanced Threat Protection (ATP) resource — file/URL malware scanning.

The ATP namespace groups three related Netskope services that all live under
the ``/api/v2/atp`` route prefix:

- **Sandbox on-demand** (``scans/*``) — submit a file for behavioural
  detonation and retrieve the analysis report by ``jobid``.
- **Threat Protection as a Service (TPaaS), file** (``tpaas/submission/*``) —
  submit a password-protected ``.zip`` for scanning and fetch its result and
  reports by ``submission_id``.
- **TPaaS URL scan** (``tpaas/urlscan/*``) — submit a URL for scanning and
  fetch its report / artifact listing by ``submission_id``.

All methods return the raw decoded JSON body as a ``dict`` (no typed models).
The transport raises :class:`~netskope.exceptions.APIError` automatically on
HTTP error statuses *and* on HTTP-200 bodies of the form
``{"status": "error", ...}``.

Example::

    # Submit a file for sandbox analysis, then poll for the report
    submission = client.atp.scan_file_path("/tmp/suspicious.zip")
    report = client.atp.get_report(submission["jobid"])
    print(report["verdict"])

    # Submit a URL for scanning
    client.atp.scan_url("https://suspicious-site.example.com/login")
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, cast

from netskope.resources._atp_response import (
    AsyncAtpResponses,
    AtpResponses,
    file_request_from_parts,
    filescan_parts,
)
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id

# All ATP services share the /api/v2/atp route prefix.
_BASE = "/api/v2/atp"

# Sandbox on-demand (atpsvc).
_FILESCAN_PATH = f"{_BASE}/scans/filescan"
_REPORTS_PATH = f"{_BASE}/scans/reports"

# TPaaS file scanning (tpaassvc).
_TPAAS_SUBMISSION = f"{_BASE}/tpaas/submission"

# TPaaS URL scanning (urlscan).
_TPAAS_URLSCAN = f"{_BASE}/tpaas/urlscan"


def _report_path(job_id: str) -> str:
    return f"{_REPORTS_PATH}/{quote_id(job_id)}"


def _submission_result_path(submission_id: str) -> str:
    return f"{_TPAAS_SUBMISSION}/{quote_id(submission_id)}/result"


def _submission_reports_path(submission_id: str) -> str:
    return f"{_TPAAS_SUBMISSION}/{quote_id(submission_id)}/reports"


def _urlscan_report_path(submission_id: str) -> str:
    return f"{_TPAAS_URLSCAN}/{quote_id(submission_id)}/report"


def _urlscan_artifacts_path(submission_id: str) -> str:
    return f"{_TPAAS_URLSCAN}/{quote_id(submission_id)}/artifacts"


class AtpResource(SyncResource):
    """Synchronous interface to the Advanced Threat Protection API."""

    @functools.cached_property
    def with_response(self) -> AtpResponses:
        return AtpResponses(self._transport)

    # -- Sandbox on-demand ---------------------------------------------------

    def scan_file(
        self,
        filename: str,
        content: bytes,
        *,
        scan_type: str = "sandbox",
    ) -> dict[str, Any]:
        """Submit a file for sandbox malware analysis.

        ``POST /scans/filescan`` is a ``multipart/form-data`` upload with the
        file as a binary ``file`` part and a required ``scantype`` query
        parameter.  *content* must be a password-protected (ZipCrypto,
        password ``infected``) ZIP holding exactly one exe/pdf/doc/xls/ppt/rtf
        member of at most 16 MB.  The response contains a ``jobid`` to pass to
        :meth:`get_report`.

        Args:
            filename: Name of the ZIP archive being submitted.
            content: Raw archive bytes.
            scan_type: Scan type; the service currently supports ``"sandbox"``.

        Returns:
            The decoded JSON body (``jobid``, ``md5``, ``sha256``, ...).

        Raises:
            netskope.exceptions.ValidationError: If the upload is not a
                supported encrypted ZIP archive.
        """
        params, files = filescan_parts(file_request_from_parts(filename, content, scan_type))
        response = self._transport.request("POST", _FILESCAN_PATH, params=params, files=files)
        return cast(dict[str, Any], response.json())

    def scan_file_path(self, path: str | Path, *, scan_type: str = "sandbox") -> dict[str, Any]:
        """Read *path* from disk and submit it via :meth:`scan_file`.

        Args:
            path: Filesystem path to the ZIP archive to submit.
            scan_type: Scan type; the service currently supports ``"sandbox"``.
        """
        p = Path(path)
        return self.scan_file(p.name, p.read_bytes(), scan_type=scan_type)

    def get_report(self, job_id: str) -> dict[str, Any]:
        """Get the sandbox analysis report for a scan job.

        Args:
            job_id: The ``jobid`` returned by :meth:`scan_file`.
        """
        return self._get(_report_path(job_id))

    # -- TPaaS file scanning -------------------------------------------------
    #
    # The TPaaS file-submit endpoints (POST /tpaas/submission/scan and
    # /scan_large) require multipart/form-data uploads.  They are not exposed
    # here because the SDK's retry layer re-reads the request body on each
    # attempt, which is incompatible with httpx's streaming multipart bodies.
    # Only the JSON result/report reads for a submission_id are supported.

    def get_scan_result(self, submission_id: str) -> dict[str, Any]:
        """Get the TPaaS scan result/verdict for a submission.

        Args:
            submission_id: The ``submission_id`` from :meth:`submit_scan`.
        """
        return self._get(_submission_result_path(submission_id))

    def get_submission_report(self, submission_id: str) -> dict[str, Any]:
        """Get the TPaaS analysis reports for a submission.

        Args:
            submission_id: The ``submission_id`` from :meth:`submit_scan`.
        """
        return self._get(_submission_reports_path(submission_id))

    # -- TPaaS URL scanning --------------------------------------------------

    def scan_url(self, url: str) -> dict[str, Any]:
        """Submit a URL for scanning.

        The response contains a ``submission_id`` for use with
        :meth:`get_url_report` and :meth:`list_url_artifacts`.

        Args:
            url: The full URL to scan (including scheme).
        """
        return self._post(f"{_TPAAS_URLSCAN}/submission/scan", json={"url": url})

    def get_url_report(self, submission_id: str) -> dict[str, Any]:
        """Get the URL-scan analysis report for a submission.

        Args:
            submission_id: The ``submission_id`` from :meth:`scan_url`.
        """
        return self._get(_urlscan_report_path(submission_id))

    def list_url_artifacts(self, submission_id: str) -> dict[str, Any]:
        """List the artifacts (pcaps, screenshots) for a URL-scan submission.

        Args:
            submission_id: The ``submission_id`` from :meth:`scan_url`.
        """
        return self._get(_urlscan_artifacts_path(submission_id))


class AsyncAtpResource(AsyncResource):
    """Asynchronous interface to the Advanced Threat Protection API."""

    @functools.cached_property
    def with_response(self) -> AsyncAtpResponses:
        return AsyncAtpResponses(self._transport)

    # -- Sandbox on-demand ---------------------------------------------------

    async def scan_file(
        self,
        filename: str,
        content: bytes,
        *,
        scan_type: str = "sandbox",
    ) -> dict[str, Any]:
        """Submit a file for sandbox malware analysis.

        See :meth:`AtpResource.scan_file`.
        """
        params, files = filescan_parts(file_request_from_parts(filename, content, scan_type))
        response = await self._transport.request("POST", _FILESCAN_PATH, params=params, files=files)
        return cast(dict[str, Any], response.json())

    async def scan_file_path(
        self, path: str | Path, *, scan_type: str = "sandbox"
    ) -> dict[str, Any]:
        """Read *path* from disk and submit it via :meth:`scan_file`."""
        p = Path(path)
        return await self.scan_file(p.name, p.read_bytes(), scan_type=scan_type)

    async def get_report(self, job_id: str) -> dict[str, Any]:
        """Get the sandbox analysis report for a scan job."""
        return await self._get(_report_path(job_id))

    # -- TPaaS file scanning -------------------------------------------------
    # (multipart file-submit endpoints are unsupported; see AtpResource.)

    async def get_scan_result(self, submission_id: str) -> dict[str, Any]:
        """Get the TPaaS scan result/verdict for a submission."""
        return await self._get(_submission_result_path(submission_id))

    async def get_submission_report(self, submission_id: str) -> dict[str, Any]:
        """Get the TPaaS analysis reports for a submission."""
        return await self._get(_submission_reports_path(submission_id))

    # -- TPaaS URL scanning --------------------------------------------------

    async def scan_url(self, url: str) -> dict[str, Any]:
        """Submit a URL for scanning.

        See :meth:`AtpResource.scan_url`.
        """
        return await self._post(f"{_TPAAS_URLSCAN}/submission/scan", json={"url": url})

    async def get_url_report(self, submission_id: str) -> dict[str, Any]:
        """Get the URL-scan analysis report for a submission."""
        return await self._get(_urlscan_report_path(submission_id))

    async def list_url_artifacts(self, submission_id: str) -> dict[str, Any]:
        """List the artifacts (pcaps, screenshots) for a URL-scan submission."""
        return await self._get(_urlscan_artifacts_path(submission_id))
