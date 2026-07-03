"""NSIQ resource — Netskope Intelligence (URL / threat intelligence) APIs.

Covers the ``/api/v2/nsiq`` gateway surface: URL category lookups, URL
re-categorization requests and their status, RetroHunt IOC (file-hash)
lookups, and false-positive submissions (URL / malware / IPS).

All methods return the raw decoded JSON body as a ``dict``.  The transport
raises :class:`~netskope.exceptions.APIError` automatically for HTTP-200
responses whose body is an error envelope (``{"status": "error", ...}``), so
callers can treat a returned dict as a success payload.

Example::

    report = client.nsiq.url_lookup("https://www.google.com")
    for entry in report.get("result", []):
        print(entry["url"], [c["name"] for c in entry.get("categories", [])])

    client.nsiq.recategorize(
        "https://example.com",
        suggested_categories=["Technology"],
        justification="Developer documentation site",
        email="me@example.com",
    )
"""

from __future__ import annotations

from typing import Any

from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id

# All NSIQ routes hang off this v2 prefix (verified against the CLI and the
# api-gateway relative paths, which resolve under /api/v2/nsiq).
_BASE = "/api/v2/nsiq"

_URLLOOKUP_PATH = f"{_BASE}/urllookup"
_RECAT_PATH = f"{_BASE}/url/recategorizations"
_RETROHUNT_GETINFO_PATH = f"{_BASE}/retrohunt/ioc/getinfo"
_RETROHUNT_INFO_PATH = f"{_BASE}/retrohunt/ioc/info"
_RETROHUNT_REPORT_PATH = f"{_BASE}/retrohunt/ioc/report"
_FP_URL_PATH = f"{_BASE}/falsepositives/url"
_FP_MALWARE_PATH = f"{_BASE}/falsepositives/malware"
_FP_IPS_PATH = f"{_BASE}/falsepositives/ips"
_FP_VALIDATE_EMAIL_PATH = f"{_BASE}/falsepositives/validations/useremail"


def _as_list(value: str | list[str]) -> list[str]:
    """Normalize a single string or an iterable of strings to ``list[str]``."""
    return [value] if isinstance(value, str) else list(value)


def _prune(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return *mapping* without any keys whose value is ``None``."""
    return {key: val for key, val in mapping.items() if val is not None}


def _build_lookup_body(
    urls: str | list[str],
    disable_dns_lookup: bool,
    category: str | None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"urls": _as_list(urls)}
    if disable_dns_lookup:
        query["disable_dns_lookup"] = True
    if category is not None:
        query["category"] = category
    return {"query": query}


def _build_recat_body(
    url: str,
    suggested_categories: list[str],
    justification: str | None,
    email: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "email": email,
        "recat_requests": [{"url": url, "suggested_categories": list(suggested_categories)}],
    }
    if justification is not None:
        body["justification"] = justification
    return body


def _build_recat_list_params(
    start_time: int | None,
    end_time: int | None,
    status: str | None,
    offset: int,
    limit: int,
    sort_by: str,
    sort_order: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "offset": offset,
        "limit": limit,
        "sortby": sort_by,
        "sortorder": sort_order,
    }
    if start_time is not None:
        params["starttime"] = start_time
    if end_time is not None:
        params["endtime"] = end_time
    if status is not None:
        params["status"] = status
    return params


def _build_fp_body(
    fp_entry: dict[str, Any], user_email: str, tenant_user_name: str | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"user_email": user_email, "fp_data": [_prune(fp_entry)]}
    if tenant_user_name is not None:
        body["tenant_user_name"] = tenant_user_name
    return body


class NsiqResource(SyncResource):
    """Synchronous interface to the Netskope Intelligence (NSIQ) API."""

    def url_lookup(
        self,
        urls: str | list[str],
        *,
        disable_dns_lookup: bool = False,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Look up web categories and URL lists for one or many URLs.

        Args:
            urls: A single URL or a list of URLs (max 100 per request).
            disable_dns_lookup: Turn off DNS resolution / IP matching.
            category: Restrict predefined categories to ``"casb"`` or ``"swg"``.

        Returns:
            The decoded response body — ``{"query": {...}, "result": [...]}``.
        """
        return self._post(
            _URLLOOKUP_PATH, json=_build_lookup_body(urls, disable_dns_lookup, category)
        )

    def recategorize(
        self,
        url: str,
        suggested_categories: list[str],
        *,
        justification: str | None = None,
        email: str = "",
    ) -> dict[str, Any]:
        """Submit a URL re-categorization request (creates a review task).

        Args:
            url: The URL to re-categorize.
            suggested_categories: Proposed categories (max 5 per URL).
            justification: Optional reason (max 2000 characters).
            email: Requester email.  Required by the gateway; defaults to an
                empty string to match the CLI's behavior.

        Returns:
            The decoded response body — ``{"status": ..., "data": {"task_id",
            "urls": [...]}}``.
        """
        return self._post(
            _RECAT_PATH, json=_build_recat_body(url, suggested_categories, justification, email)
        )

    def list_recategorizations(
        self,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 5,
        sort_by: str = "task_id",
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        """List re-categorization requests (last 90 days by default).

        Args:
            start_time: Unix epoch seconds; used with *end_time*.
            end_time: Unix epoch seconds; used with *start_time*.
            status: One of ``received``, ``inprogress``, ``completed``,
                ``rejected``.
            offset: Zero-based offset (min 0).
            limit: Max items (1-10, default 5).
            sort_by: ``task_id`` | ``start_time`` | ``end_time`` | ``status``.
            sort_order: ``asc`` | ``desc``.
        """
        params = _build_recat_list_params(
            start_time, end_time, status, offset, limit, sort_by, sort_order
        )
        return self._get(_RECAT_PATH, **params)

    def get_recategorization(self, task_id: str) -> dict[str, Any]:
        """Get a single re-categorization request by task id."""
        return self._get(f"{_RECAT_PATH}/{quote_id(task_id)}")

    def get_recategorization_url_status(self, task_id: str, url_id: str) -> dict[str, Any]:
        """Get the status of one URL within a re-categorization request."""
        return self._get(f"{_RECAT_PATH}/{quote_id(task_id)}/urls/{quote_id(url_id)}")

    def lookup_iocs(self, hashes: str | list[str]) -> dict[str, Any]:
        """RetroHunt: batch-look up sample info by file hash (md5 or sha256).

        Args:
            hashes: A single hash or a list of hashes (max 500 per request).

        Returns:
            ``{"status": ..., "result": {<hash>: {...}}}``.
        """
        return self._post(_RETROHUNT_GETINFO_PATH, json={"hash": _as_list(hashes)})

    def get_ioc(self, sample_hash: str) -> dict[str, Any]:
        """RetroHunt: get info for a single sample hash (md5 or sha256)."""
        return self._get(_RETROHUNT_INFO_PATH, hash=sample_hash)

    def get_ioc_report(self, sample_hash: str) -> dict[str, Any]:
        """RetroHunt: get the analysis report for a single sample hash."""
        return self._get(_RETROHUNT_REPORT_PATH, hash=sample_hash)

    def report_url_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        url: str | None = None,
        page: str | None = None,
        description: str | None = None,
        threat_match_value: str | None = None,
        current_category_id: list[int] | None = None,
        affected_version: str | None = None,
        timestamp: int | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit a URL false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "url": url,
            "page": page,
            "description": description,
            "threat_match_value": threat_match_value,
            "current_category_id": current_category_id,
            "affected_version": affected_version,
            "timestamp": timestamp,
        }
        return self._post(_FP_URL_PATH, json=_build_fp_body(entry, user_email, tenant_user_name))

    def report_malware_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        md5: str | None = None,
        filename: str | None = None,
        detection_name: str | None = None,
        mode: str | None = None,
        description: str | None = None,
        last_seen_time: int | None = None,
        affected_version: str | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit a malware false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "md5": md5,
            "filename": filename,
            "detection_name": detection_name,
            "mode": mode,
            "description": description,
            "last_seen_time": last_seen_time,
            "affected_version": affected_version,
        }
        return self._post(
            _FP_MALWARE_PATH, json=_build_fp_body(entry, user_email, tenant_user_name)
        )

    def report_ips_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        url: str | None = None,
        signature_id: str | None = None,
        signature_name: str | None = None,
        transaction_id: str | None = None,
        description: str | None = None,
        timestamp: int | None = None,
        affected_version: str | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit an IPS-alert false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "url": url,
            "signature_id": signature_id,
            "signature_name": signature_name,
            "transaction_id": transaction_id,
            "description": description,
            "timestamp": timestamp,
            "affected_version": affected_version,
        }
        return self._post(_FP_IPS_PATH, json=_build_fp_body(entry, user_email, tenant_user_name))

    def validate_user_email(self, user_email: str) -> dict[str, Any]:
        """Check whether *user_email* is a valid tenant user for FP submission."""
        return self._post(_FP_VALIDATE_EMAIL_PATH, json={"user_email": user_email})


class AsyncNsiqResource(AsyncResource):
    """Asynchronous interface to the Netskope Intelligence (NSIQ) API."""

    async def url_lookup(
        self,
        urls: str | list[str],
        *,
        disable_dns_lookup: bool = False,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Look up web categories and URL lists for one or many URLs.

        See :meth:`NsiqResource.url_lookup`.
        """
        return await self._post(
            _URLLOOKUP_PATH, json=_build_lookup_body(urls, disable_dns_lookup, category)
        )

    async def recategorize(
        self,
        url: str,
        suggested_categories: list[str],
        *,
        justification: str | None = None,
        email: str = "",
    ) -> dict[str, Any]:
        """Submit a URL re-categorization request.  See :meth:`NsiqResource.recategorize`."""
        return await self._post(
            _RECAT_PATH, json=_build_recat_body(url, suggested_categories, justification, email)
        )

    async def list_recategorizations(
        self,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 5,
        sort_by: str = "task_id",
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        """List re-categorization requests.  See :meth:`NsiqResource.list_recategorizations`."""
        params = _build_recat_list_params(
            start_time, end_time, status, offset, limit, sort_by, sort_order
        )
        return await self._get(_RECAT_PATH, **params)

    async def get_recategorization(self, task_id: str) -> dict[str, Any]:
        """Get a single re-categorization request by task id."""
        return await self._get(f"{_RECAT_PATH}/{quote_id(task_id)}")

    async def get_recategorization_url_status(self, task_id: str, url_id: str) -> dict[str, Any]:
        """Get the status of one URL within a re-categorization request."""
        return await self._get(f"{_RECAT_PATH}/{quote_id(task_id)}/urls/{quote_id(url_id)}")

    async def lookup_iocs(self, hashes: str | list[str]) -> dict[str, Any]:
        """RetroHunt: batch sample-info lookup by hash.  See :meth:`NsiqResource.lookup_iocs`."""
        return await self._post(_RETROHUNT_GETINFO_PATH, json={"hash": _as_list(hashes)})

    async def get_ioc(self, sample_hash: str) -> dict[str, Any]:
        """RetroHunt: get info for a single sample hash (md5 or sha256)."""
        return await self._get(_RETROHUNT_INFO_PATH, hash=sample_hash)

    async def get_ioc_report(self, sample_hash: str) -> dict[str, Any]:
        """RetroHunt: get the analysis report for a single sample hash."""
        return await self._get(_RETROHUNT_REPORT_PATH, hash=sample_hash)

    async def report_url_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        url: str | None = None,
        page: str | None = None,
        description: str | None = None,
        threat_match_value: str | None = None,
        current_category_id: list[int] | None = None,
        affected_version: str | None = None,
        timestamp: int | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit a URL false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "url": url,
            "page": page,
            "description": description,
            "threat_match_value": threat_match_value,
            "current_category_id": current_category_id,
            "affected_version": affected_version,
            "timestamp": timestamp,
        }
        return await self._post(
            _FP_URL_PATH, json=_build_fp_body(entry, user_email, tenant_user_name)
        )

    async def report_malware_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        md5: str | None = None,
        filename: str | None = None,
        detection_name: str | None = None,
        mode: str | None = None,
        description: str | None = None,
        last_seen_time: int | None = None,
        affected_version: str | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit a malware false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "md5": md5,
            "filename": filename,
            "detection_name": detection_name,
            "mode": mode,
            "description": description,
            "last_seen_time": last_seen_time,
            "affected_version": affected_version,
        }
        return await self._post(
            _FP_MALWARE_PATH, json=_build_fp_body(entry, user_email, tenant_user_name)
        )

    async def report_ips_false_positive(
        self,
        incident_id: str,
        user_email: str,
        *,
        url: str | None = None,
        signature_id: str | None = None,
        signature_name: str | None = None,
        transaction_id: str | None = None,
        description: str | None = None,
        timestamp: int | None = None,
        affected_version: str | None = None,
        tenant_user_name: str | None = None,
    ) -> dict[str, Any]:
        """Submit an IPS-alert false-positive report (creates a review ticket)."""
        entry = {
            "incident_id": incident_id,
            "url": url,
            "signature_id": signature_id,
            "signature_name": signature_name,
            "transaction_id": transaction_id,
            "description": description,
            "timestamp": timestamp,
            "affected_version": affected_version,
        }
        return await self._post(
            _FP_IPS_PATH, json=_build_fp_body(entry, user_email, tenant_user_name)
        )

    async def validate_user_email(self, user_email: str) -> dict[str, Any]:
        """Check whether *user_email* is a valid tenant user for FP submission."""
        return await self._post(_FP_VALIDATE_EMAIL_PATH, json={"user_email": user_email})
