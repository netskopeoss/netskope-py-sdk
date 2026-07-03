"""SPM resource — SaaS Security Posture Management.

SPM assesses the security posture of connected SaaS applications: it scores
each app against posture rules, tracks configuration drift, and exposes an
inventory of discovered SaaS resources.  All methods return the raw JSON
response body as a ``dict`` (no typed models), so forward-compatible fields
are preserved verbatim.

Example::

    apps = client.spm.list_apps()
    detail = client.spm.get_app("Microsoft 365")
    score = client.spm.posture_score()

Note:
    ``client.spm`` may not be wired in every SDK build; instantiate the
    resource directly against a client's transport when it is not::

        from netskope.resources.spm import SpmResource

        spm = SpmResource(client._transport)
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from netskope.resources._base import AsyncResource, SyncResource

_APPS_PATH = "/api/v2/spm/apps"
_INVENTORY_PATH = "/api/v2/spm/inventory"
_POSTURE_SCORE_PATH = "/api/v2/spm/saas_posture_score"
_POLICY_RULES_PATH = "/api/v2/spm/policy/rules"
_RECENT_CHANGES_PATH = "/api/v2/spm/apps/recentchanges/getstats"


def _app_path(app_name: str) -> str:
    """Build the per-app path, percent-encoding *app_name* as one segment.

    SPM app names contain spaces (e.g. ``"Microsoft 365"``), so the strict
    :func:`~netskope.resources._extract.quote_id` (which rejects whitespace)
    cannot be used — encode with :func:`urllib.parse.quote` and ``safe=""``
    so spaces become ``%20`` and any ``/`` cannot alter the request path.
    """
    return f"{_APPS_PATH}/{urllib.parse.quote(app_name, safe='')}"


def _inventory_body(filter: str | None) -> dict[str, Any] | None:
    """Build the inventory request body.

    Returns ``{"filter": <str>}`` when a filter is supplied, otherwise
    ``None`` (empty body), matching the SPM inventory contract.
    """
    if filter is None:
        return None
    return {"filter": filter}


class SpmResource(SyncResource):
    """Synchronous interface to the SaaS Security Posture Management API."""

    def list_apps(self) -> dict[str, Any]:
        """List all SaaS applications monitored by SPM.

        Returns:
            The raw response body from ``GET /api/v2/spm/apps``.
        """
        return self._get(_APPS_PATH)

    def get_app(self, app_name: str) -> dict[str, Any]:
        """Get posture details for a single SaaS application.

        Args:
            app_name: The application name exactly as it appears in the SPM
                dashboard (e.g. ``"Microsoft 365"``, ``"Salesforce"``).
                Spaces and other characters are percent-encoded for you.
        """
        return self._get(_app_path(app_name))

    def inventory(self, *, filter: str | None = None) -> dict[str, Any]:
        """Query the SaaS application inventory.

        Args:
            filter: Optional filter expression passed straight through to the
                API in the request body as ``{"filter": <str>}``.  When
                ``None`` (default) the inventory is queried with no filter.
        """
        return self._post(_INVENTORY_PATH, json=_inventory_body(filter))

    def posture_score(self) -> dict[str, Any]:
        """Get the aggregated SaaS security posture score for the tenant.

        Returns:
            The raw response body from ``GET /api/v2/spm/saas_posture_score``.
        """
        return self._get(_POSTURE_SCORE_PATH)

    def list_policy_rules(self) -> dict[str, Any]:
        """List all posture policy rules configured in SPM.

        Returns:
            The raw response body from ``GET /api/v2/spm/policy/rules``.
        """
        return self._get(_POLICY_RULES_PATH)

    def recent_changes(self) -> dict[str, Any]:
        """Get statistics on recent SaaS configuration changes.

        Returns:
            The raw response body from
            ``GET /api/v2/spm/apps/recentchanges/getstats``.
        """
        return self._get(_RECENT_CHANGES_PATH)


class AsyncSpmResource(AsyncResource):
    """Asynchronous interface to the SaaS Security Posture Management API."""

    async def list_apps(self) -> dict[str, Any]:
        """List all SaaS applications monitored by SPM.

        See :meth:`SpmResource.list_apps`.
        """
        return await self._get(_APPS_PATH)

    async def get_app(self, app_name: str) -> dict[str, Any]:
        """Get posture details for a single SaaS application.

        See :meth:`SpmResource.get_app`.
        """
        return await self._get(_app_path(app_name))

    async def inventory(self, *, filter: str | None = None) -> dict[str, Any]:
        """Query the SaaS application inventory.

        See :meth:`SpmResource.inventory`.
        """
        return await self._post(_INVENTORY_PATH, json=_inventory_body(filter))

    async def posture_score(self) -> dict[str, Any]:
        """Get the aggregated SaaS security posture score for the tenant.

        See :meth:`SpmResource.posture_score`.
        """
        return await self._get(_POSTURE_SCORE_PATH)

    async def list_policy_rules(self) -> dict[str, Any]:
        """List all posture policy rules configured in SPM.

        See :meth:`SpmResource.list_policy_rules`.
        """
        return await self._get(_POLICY_RULES_PATH)

    async def recent_changes(self) -> dict[str, Any]:
        """Get statistics on recent SaaS configuration changes.

        See :meth:`SpmResource.recent_changes`.
        """
        return await self._get(_RECENT_CHANGES_PATH)
