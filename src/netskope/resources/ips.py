"""IPS resource — Intrusion Prevention System configuration and signatures.

Covers the ``/api/v2/ips`` endpoints: feature status, allowlist, signature
reference list and filtered signature search, Alert Only mode, signature
overrides, the user notification template, and threat hunting config.

All methods return the raw response body as a ``dict`` — the transport
raises :class:`~netskope.exceptions.APIError` for error responses, so a
returned dict always represents a successful call.

Example::

    status = client.ips.status()
    print(status["data"])  # {"web": true, "nonweb": true, "npa": false}

    refs = client.ips.list_signatures(limit=20)
    for ref in refs["data"]:
        print(ref)  # e.g. "bid:15208"
"""

from __future__ import annotations

from typing import Any

from netskope.exceptions import ValidationError
from netskope.resources._base import AsyncResource, SyncResource

_STATUS_PATH = "/api/v2/ips/status"
_ALLOWLIST_PATH = "/api/v2/ips/allowlist"
_SIGNATURE_REFERENCE_PATH = "/api/v2/ips/signaturereferencelist"
_SIGNATURE_SEARCH_PATH = "/api/v2/ips/getsignaturelist"
_ALERT_ONLY_MODE_PATH = "/api/v2/ips/alertonlymode"
_SIGNATURE_OVERRIDES_PATH = "/api/v2/ips/signatureoverrides"
_DELETE_SIGNATURE_OVERRIDES_PATH = "/api/v2/ips/deletesignatureoverrides"
_NOTIFICATION_TEMPLATE_PATH = "/api/v2/ips/notificationtemplate"
_THREAT_HUNTING_CONFIG_PATH = "/api/v2/ips/threathuntingconfig"

_VALID_OVERRIDE_ACTIONS = ("disabled", "alert", "reject")
_VALID_TRAFFIC_TYPES = ("web", "nonweb")


def _build_status_payload(
    web: bool | None,
    nonweb: bool | None,
    npa: bool | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if web is not None:
        payload["web"] = web
    if nonweb is not None:
        payload["nonweb"] = nonweb
    if npa is not None:
        payload["npa"] = npa
    if not payload:
        raise ValidationError("At least one of web, nonweb, or npa must be provided.")
    return payload


def _build_allowlist_payload(
    src_ids: list[str] | None,
    domain: list[str] | None,
    dst_ids: list[str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if src_ids is not None:
        payload["src_ids"] = list(src_ids)
    if domain is not None:
        payload["domain"] = list(domain)
    if dst_ids is not None:
        payload["dst_ids"] = list(dst_ids)
    if not payload:
        raise ValidationError("At least one of src_ids, domain, or dst_ids must be provided.")
    return payload


def _build_reference_params(
    limit: int | None,
    offset: int | None,
    reference: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if reference is not None:
        params["reference"] = reference
    return params


def _build_paging_params(limit: int | None, offset: int | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return params


def _build_signature_search_payload(
    limit: int | None,
    offset: int | None,
    reference: list[str] | None,
    cvss_severity: list[str] | None,
    traffic_type: list[str] | None,
    sig_id: str | None,
    name: str | None,
    keyword: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if limit is not None:
        payload["limit"] = limit
    if offset is not None:
        payload["offset"] = offset
    filters: dict[str, Any] = {}
    if reference is not None:
        filters["reference"] = list(reference)
    if cvss_severity is not None:
        filters["cvss_severity"] = list(cvss_severity)
    if traffic_type is not None:
        invalid = [t for t in traffic_type if t not in _VALID_TRAFFIC_TYPES]
        if invalid:
            raise ValidationError(
                f"Invalid traffic_type value(s): {', '.join(invalid)}. "
                f"Must be one of: {', '.join(_VALID_TRAFFIC_TYPES)}"
            )
        filters["traffic_type"] = list(traffic_type)
    if sig_id is not None:
        filters["sig_id"] = sig_id
    if name is not None:
        filters["name"] = name
    if keyword is not None:
        filters["keyword"] = keyword
    if filters:
        payload["filter"] = filters
    return payload


def _build_overrides_payload(sig_ids: list[str], override: str) -> dict[str, Any]:
    if not sig_ids:
        raise ValidationError("sig_ids must contain at least one signature ID.")
    if override not in _VALID_OVERRIDE_ACTIONS:
        raise ValidationError(
            f"Invalid override {override!r}. Must be one of: {', '.join(_VALID_OVERRIDE_ACTIONS)}"
        )
    return {"sig_id": list(sig_ids), "override": override}


def _build_delete_overrides_payload(sig_ids: list[str]) -> dict[str, Any]:
    if not sig_ids:
        raise ValidationError("sig_ids must contain at least one signature ID.")
    return {"sig_id": list(sig_ids)}


def _build_notification_template_payload(template_file_name: str) -> dict[str, Any]:
    if not template_file_name:
        raise ValidationError("template_file_name must not be empty.")
    return {"web": {"template_file_name": template_file_name}}


def _build_threat_hunting_payload(
    beacon_detection: bool | None,
    html_smuggling: bool | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if beacon_detection is not None:
        payload["beacon_detection"] = {"enabled": beacon_detection}
    if html_smuggling is not None:
        payload["html_smuggling"] = {"enabled": html_smuggling}
    if not payload:
        raise ValidationError(
            "At least one of beacon_detection or html_smuggling must be provided."
        )
    return payload


class IpsResource(SyncResource):
    """Synchronous interface to the IPS API."""

    def status(self) -> dict[str, Any]:
        """Get the IPS feature status.

        Returns:
            The response body; ``data`` holds per-traffic-type booleans
            (``web``, ``nonweb``, ``npa``).
        """
        return self._get(_STATUS_PATH)

    def update_status(
        self,
        *,
        web: bool | None = None,
        nonweb: bool | None = None,
        npa: bool | None = None,
    ) -> dict[str, Any]:
        """Update the IPS feature status per traffic type.

        Only the provided flags are sent; omitted flags are left unchanged.

        Args:
            web: Enable/disable IPS for Web traffic.
            nonweb: Enable/disable IPS for Non-Web traffic.
            npa: Enable/disable IPS for NPA traffic.

        Raises:
            netskope.exceptions.ValidationError: If no flag is provided.
        """
        return self._patch(_STATUS_PATH, json=_build_status_payload(web, nonweb, npa))

    def list_allowlist(self) -> dict[str, Any]:
        """Get the IPS allowlist.

        Returns:
            The response body; ``data`` holds ``src_ids`` (source network
            location IDs), ``domain`` (domain list), and ``dst_ids``
            (destination network location IDs).
        """
        return self._get(_ALLOWLIST_PATH)

    def update_allowlist(
        self,
        *,
        src_ids: list[str] | None = None,
        domain: list[str] | None = None,
        dst_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update the IPS allowlist (PATCH — only provided fields change).

        Each provided list replaces that field's current value in full;
        pass an empty list to clear a field.  To remove a single entry,
        fetch the current allowlist, drop the entry, and PATCH the result.

        Args:
            src_ids: Source network location IDs to allowlist.
            domain: Domains to allowlist.
            dst_ids: Destination network location IDs to allowlist.

        Raises:
            netskope.exceptions.ValidationError: If no field is provided.
        """
        return self._patch(_ALLOWLIST_PATH, json=_build_allowlist_payload(src_ids, domain, dst_ids))

    def list_signatures(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """List IPS signature references.

        Args:
            limit: Max items to retrieve (API default 10, max 100).
            offset: Zero-based offset of the first item (API default 0).
            reference: Search keyword for signature references.

        Returns:
            The response body; ``data`` is a list of reference strings
            (e.g. ``"bid:15208"``, ``"cve:cve-2012-3993"``).
        """
        return self._get(
            _SIGNATURE_REFERENCE_PATH, **_build_reference_params(limit, offset, reference)
        )

    def search_signatures(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        reference: list[str] | None = None,
        cvss_severity: list[str] | None = None,
        traffic_type: list[str] | None = None,
        sig_id: str | None = None,
        name: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        """Search the signature list with filters.

        Args:
            limit: Max items to retrieve (API default 10, max 100).
            offset: Zero-based offset of the first item (API default 0).
            reference: Reference IDs to filter by.
            cvss_severity: CVSS severity levels to filter by
                (e.g. ``["critical", "high"]``).
            traffic_type: Traffic types to filter by (``"web"``/``"nonweb"``).
            sig_id: Partial signature ID string.
            name: Partial signature name string.
            keyword: Partial signature ID or name string.

        Returns:
            The response body; ``data`` holds ``total`` and ``signature``
            (a list of signature detail objects).

        Raises:
            netskope.exceptions.ValidationError: If *traffic_type* contains
                an unsupported value.
        """
        payload = _build_signature_search_payload(
            limit, offset, reference, cvss_severity, traffic_type, sig_id, name, keyword
        )
        return self._post(_SIGNATURE_SEARCH_PATH, json=payload)

    def get_alert_only_mode(self) -> dict[str, Any]:
        """Get the IPS Alert Only mode status."""
        return self._get(_ALERT_ONLY_MODE_PATH)

    def set_alert_only_mode(self, enabled: bool) -> dict[str, Any]:
        """Enable or disable IPS Alert Only mode.

        Args:
            enabled: ``True`` to alert without blocking; ``False`` to
                enforce signature actions.
        """
        return self._put(_ALERT_ONLY_MODE_PATH, json={"enabled": enabled})

    def list_signature_overrides(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List IPS signature overrides.

        Args:
            limit: Max items to retrieve (API default 10, max 100).
            offset: Zero-based offset of the first item (API default 0).

        Returns:
            The response body; ``data`` holds ``total`` and ``overrides``.
        """
        return self._get(_SIGNATURE_OVERRIDES_PATH, **_build_paging_params(limit, offset))

    def update_signature_overrides(
        self,
        sig_ids: list[str],
        override: str,
    ) -> dict[str, Any]:
        """Override the action for the given signatures.

        Args:
            sig_ids: Signature IDs to override.
            override: New action — one of ``"disabled"``, ``"alert"``,
                or ``"reject"``.

        Raises:
            netskope.exceptions.ValidationError: If *sig_ids* is empty or
                *override* is not a supported action.
        """
        return self._put(
            _SIGNATURE_OVERRIDES_PATH, json=_build_overrides_payload(sig_ids, override)
        )

    def delete_signature_overrides(self, sig_ids: list[str]) -> dict[str, Any]:
        """Remove overrides for the given signatures (restores defaults).

        Args:
            sig_ids: Signature IDs whose overrides should be removed.

        Raises:
            netskope.exceptions.ValidationError: If *sig_ids* is empty.
        """
        return self._post(
            _DELETE_SIGNATURE_OVERRIDES_PATH, json=_build_delete_overrides_payload(sig_ids)
        )

    def get_notification_template(self) -> dict[str, Any]:
        """Get the IPS user notification template."""
        return self._get(_NOTIFICATION_TEMPLATE_PATH)

    def update_notification_template(self, template_file_name: str) -> dict[str, Any]:
        """Set the IPS user notification template for Web IPS.

        Args:
            template_file_name: Template file name (e.g. ``"11.html"``).

        Raises:
            netskope.exceptions.ValidationError: If *template_file_name*
                is empty.
        """
        return self._patch(
            _NOTIFICATION_TEMPLATE_PATH,
            json=_build_notification_template_payload(template_file_name),
        )

    def get_threat_hunting_config(self) -> dict[str, Any]:
        """Get the IPS threat hunting configuration."""
        return self._get(_THREAT_HUNTING_CONFIG_PATH)

    def update_threat_hunting_config(
        self,
        *,
        beacon_detection: bool | None = None,
        html_smuggling: bool | None = None,
    ) -> dict[str, Any]:
        """Update the IPS threat hunting configuration.

        Args:
            beacon_detection: Enable/disable beacon detection.
            html_smuggling: Enable/disable HTML smuggling detection.

        Raises:
            netskope.exceptions.ValidationError: If no flag is provided.
        """
        return self._patch(
            _THREAT_HUNTING_CONFIG_PATH,
            json=_build_threat_hunting_payload(beacon_detection, html_smuggling),
        )


class AsyncIpsResource(AsyncResource):
    """Asynchronous interface to the IPS API."""

    async def status(self) -> dict[str, Any]:
        """Get the IPS feature status."""
        return await self._get(_STATUS_PATH)

    async def update_status(
        self,
        *,
        web: bool | None = None,
        nonweb: bool | None = None,
        npa: bool | None = None,
    ) -> dict[str, Any]:
        """Update the IPS feature status per traffic type.

        See :meth:`IpsResource.update_status`.
        """
        return await self._patch(_STATUS_PATH, json=_build_status_payload(web, nonweb, npa))

    async def list_allowlist(self) -> dict[str, Any]:
        """Get the IPS allowlist (``src_ids``, ``domain``, ``dst_ids``)."""
        return await self._get(_ALLOWLIST_PATH)

    async def update_allowlist(
        self,
        *,
        src_ids: list[str] | None = None,
        domain: list[str] | None = None,
        dst_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update the IPS allowlist (PATCH — only provided fields change).

        See :meth:`IpsResource.update_allowlist`.
        """
        return await self._patch(
            _ALLOWLIST_PATH, json=_build_allowlist_payload(src_ids, domain, dst_ids)
        )

    async def list_signatures(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """List IPS signature references.

        See :meth:`IpsResource.list_signatures`.
        """
        return await self._get(
            _SIGNATURE_REFERENCE_PATH, **_build_reference_params(limit, offset, reference)
        )

    async def search_signatures(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        reference: list[str] | None = None,
        cvss_severity: list[str] | None = None,
        traffic_type: list[str] | None = None,
        sig_id: str | None = None,
        name: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        """Search the signature list with filters.

        See :meth:`IpsResource.search_signatures`.
        """
        payload = _build_signature_search_payload(
            limit, offset, reference, cvss_severity, traffic_type, sig_id, name, keyword
        )
        return await self._post(_SIGNATURE_SEARCH_PATH, json=payload)

    async def get_alert_only_mode(self) -> dict[str, Any]:
        """Get the IPS Alert Only mode status."""
        return await self._get(_ALERT_ONLY_MODE_PATH)

    async def set_alert_only_mode(self, enabled: bool) -> dict[str, Any]:
        """Enable or disable IPS Alert Only mode."""
        return await self._put(_ALERT_ONLY_MODE_PATH, json={"enabled": enabled})

    async def list_signature_overrides(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List IPS signature overrides.

        See :meth:`IpsResource.list_signature_overrides`.
        """
        return await self._get(_SIGNATURE_OVERRIDES_PATH, **_build_paging_params(limit, offset))

    async def update_signature_overrides(
        self,
        sig_ids: list[str],
        override: str,
    ) -> dict[str, Any]:
        """Override the action for the given signatures.

        See :meth:`IpsResource.update_signature_overrides`.
        """
        return await self._put(
            _SIGNATURE_OVERRIDES_PATH, json=_build_overrides_payload(sig_ids, override)
        )

    async def delete_signature_overrides(self, sig_ids: list[str]) -> dict[str, Any]:
        """Remove overrides for the given signatures (restores defaults)."""
        return await self._post(
            _DELETE_SIGNATURE_OVERRIDES_PATH, json=_build_delete_overrides_payload(sig_ids)
        )

    async def get_notification_template(self) -> dict[str, Any]:
        """Get the IPS user notification template."""
        return await self._get(_NOTIFICATION_TEMPLATE_PATH)

    async def update_notification_template(self, template_file_name: str) -> dict[str, Any]:
        """Set the IPS user notification template for Web IPS.

        See :meth:`IpsResource.update_notification_template`.
        """
        return await self._patch(
            _NOTIFICATION_TEMPLATE_PATH,
            json=_build_notification_template_payload(template_file_name),
        )

    async def get_threat_hunting_config(self) -> dict[str, Any]:
        """Get the IPS threat hunting configuration."""
        return await self._get(_THREAT_HUNTING_CONFIG_PATH)

    async def update_threat_hunting_config(
        self,
        *,
        beacon_detection: bool | None = None,
        html_smuggling: bool | None = None,
    ) -> dict[str, Any]:
        """Update the IPS threat hunting configuration.

        See :meth:`IpsResource.update_threat_hunting_config`.
        """
        return await self._patch(
            _THREAT_HUNTING_CONFIG_PATH,
            json=_build_threat_hunting_payload(beacon_detection, html_smuggling),
        )
