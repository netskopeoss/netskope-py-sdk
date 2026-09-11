"""Canonical, non-replayed ATP submissions and typed report access."""

from __future__ import annotations

from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import ValidationError
from netskope.models.atp import (
    AtpFileScan,
    AtpFileSubmission,
    AtpScanReport,
    AtpSubmissionReport,
    AtpUrlScan,
    AtpUrlSubmission,
)
from netskope.resources._admin_response import item, request_payload
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id
from netskope.response import ApiResponse


def _file_request(request: AtpFileScan) -> AtpFileScan:
    try:
        return AtpFileScan.model_validate(request)
    except ModelValidationError:
        raise ValidationError(
            "Invalid sandbox upload: provide a supported, encrypted ZIP archive."
        ) from None


class AtpResponses(SyncResource):
    def scan_file(self, request: AtpFileScan) -> ApiResponse[AtpFileSubmission]:
        request = _file_request(request)
        response = self._transport.request(
            "POST",
            "/api/v2/atp/scans/filescan",
            params={"scantype": request.scan_type},
            files={"file": (request.filename, request.content, "application/zip")},
        )
        return ApiResponse(response, lambda raw: item(raw, AtpFileSubmission))

    def scan_url(self, request: AtpUrlScan) -> ApiResponse[AtpUrlSubmission]:
        response = self._transport.request(
            "POST",
            "/api/v2/atp/tpaas/urlscan/submission/scan",
            json=request_payload(request, AtpUrlScan),
        )
        return ApiResponse(response, lambda raw: item(raw, AtpUrlSubmission))

    def get_report(self, job_id: str) -> ApiResponse[AtpScanReport]:
        response = self._transport.request("GET", f"/api/v2/atp/scans/reports/{quote_id(job_id)}")
        return ApiResponse(response, lambda raw: item(raw, AtpScanReport))

    def get_submission_report(self, submission_id: str) -> ApiResponse[AtpSubmissionReport]:
        response = self._transport.request(
            "GET", f"/api/v2/atp/tpaas/submission/{quote_id(submission_id)}/reports"
        )
        return ApiResponse(response, lambda raw: item(raw, AtpSubmissionReport))


class AsyncAtpResponses(AsyncResource):
    async def scan_file(self, request: AtpFileScan) -> ApiResponse[AtpFileSubmission]:
        request = _file_request(request)
        response = await self._transport.request(
            "POST",
            "/api/v2/atp/scans/filescan",
            params={"scantype": request.scan_type},
            files={"file": (request.filename, request.content, "application/zip")},
        )
        return ApiResponse(response, lambda raw: item(raw, AtpFileSubmission))

    async def scan_url(self, request: AtpUrlScan) -> ApiResponse[AtpUrlSubmission]:
        response = await self._transport.request(
            "POST",
            "/api/v2/atp/tpaas/urlscan/submission/scan",
            json=request_payload(request, AtpUrlScan),
        )
        return ApiResponse(response, lambda raw: item(raw, AtpUrlSubmission))

    async def get_report(self, job_id: str) -> ApiResponse[AtpScanReport]:
        response = await self._transport.request(
            "GET", f"/api/v2/atp/scans/reports/{quote_id(job_id)}"
        )
        return ApiResponse(response, lambda raw: item(raw, AtpScanReport))

    async def get_submission_report(self, submission_id: str) -> ApiResponse[AtpSubmissionReport]:
        response = await self._transport.request(
            "GET", f"/api/v2/atp/tpaas/submission/{quote_id(submission_id)}/reports"
        )
        return ApiResponse(response, lambda raw: item(raw, AtpSubmissionReport))
