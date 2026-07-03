"""RBI resource — Remote Browser Isolation configuration and templates.

Remote Browser Isolation (RBI) renders risky web content in an isolated cloud
browser and streams only safe pixels to the user.  This namespace exposes the
RBI reference data (applications, supported browsers, default categories), the
isolation *templates* that define per-session security controls, and the
tenant-wide Cloud Storage and Content Disarm & Reconstruction (CDR) settings.

Responses are returned as plain ``dict`` objects (the raw API envelope,
typically ``{"status": ..., "message": ..., ...}``) because RBI schemas vary by
tenant license and feature flags.  The transport raises
:class:`~netskope.exceptions.APIError` automatically when the API replies with
an HTTP 200 body whose ``status`` is ``"error"``.

Example::

    # Reference data
    apps = client.rbi.list_applications()
    browsers = client.rbi.list_supported_browsers()
    categories = client.rbi.list_default_categories()

    # Templates
    for_page = client.rbi.list_templates(limit=10)
    template = client.rbi.get_template("e2cbba33-5ffc-4b0a-a4ae-3d58ce82d186")
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id

_RBI_PATH = "/api/v2/rbi"
_APPLICATIONS_PATH = f"{_RBI_PATH}/applications"
_BROWSERS_PATH = f"{_RBI_PATH}/browsers/supported"
_CATEGORIES_PATH = f"{_RBI_PATH}/categories/default"
_TEMPLATES_PATH = f"{_RBI_PATH}/templates"
_TEMPLATES_DEFAULT_PATH = f"{_TEMPLATES_PATH}/default"
_TEMPLATES_DIFFS_PATH = f"{_TEMPLATES_PATH}/diffs"
_TEMPLATES_DEPLOY_PATH = f"{_TEMPLATES_PATH}/deploy"
_TEMPLATES_REVERT_PATH = f"{_TEMPLATES_PATH}/revert"
_CLOUDSTORAGE_PATH = f"{_RBI_PATH}/cloudstorage"
_CLOUDSTORAGE_DEFAULT_PATH = f"{_CLOUDSTORAGE_PATH}/default"
_CLOUDSTORAGE_INVALIDATE_PATH = f"{_CLOUDSTORAGE_PATH}/invalidate"
_CDR_PATH = f"{_RBI_PATH}/cdr"
_CDR_DEFAULT_PATH = f"{_CDR_PATH}/default"
_CDR_VENDORS_PATH = f"{_CDR_PATH}/vendors"
_CDR_TESTCONFIG_PATH = f"{_CDR_PATH}/testconfig"


def _template_path(template_id: str) -> str:
    return f"{_TEMPLATES_PATH}/{validate_id(template_id, 'template_id')}"


def _build_templates_params(
    name: str | None,
    limit: int | None,
    offset: int | None,
    sort_by: str | None,
    sort_order: str | None,
    status: builtins.list[str] | None,
    fields: builtins.list[str] | None,
) -> dict[str, Any]:
    """Build the query params for ``GET /rbi/templates``.

    ``status`` and ``fields`` are serialized as comma-separated lists
    (OpenAPI ``style=form, explode=false``).
    """
    params: dict[str, Any] = {}
    if name is not None:
        params["name"] = name
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if sort_by is not None:
        params["sortby"] = sort_by
    if sort_order is not None:
        params["sortorder"] = sort_order
    if status is not None:
        params["status"] = ",".join(status)
    if fields is not None:
        params["fields"] = ",".join(fields)
    return params


def _build_deploy_body(
    template_ids: builtins.list[str] | None,
    note: str | None,
) -> dict[str, Any] | None:
    body: dict[str, Any] = {}
    if template_ids is not None:
        body["template_ids"] = list(template_ids)
    if note is not None:
        body["note"] = note
    return body or None


class RbiResource(SyncResource):
    """Synchronous interface to the Remote Browser Isolation API."""

    # -- Reference data ----------------------------------------------------

    def list_applications(self) -> dict[str, Any]:
        """List application names and account types RBI supports.

        Maps to ``GET /api/v2/rbi/applications``.  Returns an object keyed by
        application (e.g. ``google``, ``microsoft``) — it is not paginated.
        """
        return self._get(_APPLICATIONS_PATH)

    def list_supported_browsers(self) -> dict[str, Any]:
        """List the browsers supported for isolated rendering.

        Maps to ``GET /api/v2/rbi/browsers/supported``.
        """
        return self._get(_BROWSERS_PATH)

    def list_default_categories(self) -> dict[str, Any]:
        """List the URL categories that are isolated by default.

        Maps to ``GET /api/v2/rbi/categories/default``.
        """
        return self._get(_CATEGORIES_PATH)

    # -- Templates (read) --------------------------------------------------

    def list_templates(
        self,
        *,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        status: builtins.list[str] | None = None,
        fields: builtins.list[str] | None = None,
    ) -> dict[str, Any]:
        """List isolation templates matching the query parameters.

        Maps to ``GET /api/v2/rbi/templates``.

        Args:
            name: Filter results by template name.
            limit: Maximum number of results (``0`` means unlimited).
            offset: Zero-based offset of the first item to return.
            sort_by: Sort field — one of ``template_id``, ``template_name``,
                ``template_status``, ``modification_time``.
            sort_order: ``"asc"`` or ``"desc"``.
            status: Filter by ``template_status`` — any of ``applied``,
                ``pending-create``, ``pending-delete``, ``pending-update``.
            fields: ``template_data`` fields to include in each item.
        """
        params = _build_templates_params(name, limit, offset, sort_by, sort_order, status, fields)
        return self._get(_TEMPLATES_PATH, **params)

    def get_template(self, template_id: str) -> dict[str, Any]:
        """Get a single isolation template by id.

        Maps to ``GET /api/v2/rbi/templates/{id}``.  The id is a UUID string.
        """
        return self._get(_template_path(template_id))

    def get_default_template(self) -> dict[str, Any]:
        """Get the contents of the default template.

        Maps to ``GET /api/v2/rbi/templates/default``.
        """
        return self._get(_TEMPLATES_DEFAULT_PATH)

    def list_template_diffs(self) -> dict[str, Any]:
        """Get pending changes (diffs) for all templates.

        Maps to ``GET /api/v2/rbi/templates/diffs``.
        """
        return self._get(_TEMPLATES_DIFFS_PATH)

    def get_template_diffs(self, template_id: str) -> dict[str, Any]:
        """Get pending changes (diffs) for a single template.

        Maps to ``GET /api/v2/rbi/templates/{id}/diffs``.
        """
        return self._get(f"{_template_path(template_id)}/diffs")

    # -- Templates (write) -------------------------------------------------

    def create_template(self, template_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new template (pending deploy).

        Maps to ``POST /api/v2/rbi/templates``.

        Args:
            template_data: The full ``TemplateData`` body (all fields required).
        """
        return self._post(_TEMPLATES_PATH, json=template_data)

    def update_template(self, template_id: str, template_data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing template (pending deploy).

        Maps to ``PATCH /api/v2/rbi/templates/{id}``.  Accepts a partial
        ``TemplatePatchData`` body; at least one supported field is required.
        """
        return self._patch(_template_path(template_id), json=template_data)

    def delete_template(self, template_id: str) -> dict[str, Any]:
        """Delete a template (pending deploy).

        Maps to ``DELETE /api/v2/rbi/templates/{id}``.
        """
        return self._delete(_template_path(template_id))

    def restore_template(self, template_id: str) -> dict[str, Any]:
        """Restore a template to the default template values (pending deploy).

        Maps to ``POST /api/v2/rbi/templates/{id}/default``.
        """
        return self._post(f"{_template_path(template_id)}/default")

    def deploy_templates(
        self,
        template_ids: builtins.list[str] | None = None,
        *,
        deploy_all: bool = False,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending changes for the specified templates.

        Maps to ``POST /api/v2/rbi/templates/deploy``.  Provide exactly one of
        *template_ids* (in the body) or ``deploy_all=True`` (the ``all=true``
        query parameter).

        Args:
            template_ids: Template UUIDs whose pending changes to deploy.
            deploy_all: When ``True``, deploy all templates with pending
                changes (sends ``?all=true``).
            note: Optional audit-log description.
        """
        body = _build_deploy_body(template_ids, note)
        params: dict[str, Any] = {"all": True} if deploy_all else {}
        return self._post(_TEMPLATES_DEPLOY_PATH, json=body, **params)

    def revert_templates(self, template_ids: builtins.list[str]) -> dict[str, Any]:
        """Discard pending changes for the specified templates.

        Maps to ``POST /api/v2/rbi/templates/revert``.
        """
        return self._post(_TEMPLATES_REVERT_PATH, json={"template_ids": list(template_ids)})

    # -- Cloud storage -----------------------------------------------------

    def get_cloud_storage(self) -> dict[str, Any]:
        """Get the Cloud Storage configuration.

        Maps to ``GET /api/v2/rbi/cloudstorage``.
        """
        return self._get(_CLOUDSTORAGE_PATH)

    def update_cloud_storage(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update the Cloud Storage configuration (partial update).

        Maps to ``PATCH /api/v2/rbi/cloudstorage``.
        """
        return self._patch(_CLOUDSTORAGE_PATH, json=config)

    def restore_cloud_storage(self) -> dict[str, Any]:
        """Restore the Cloud Storage configuration to default values.

        Maps to ``POST /api/v2/rbi/cloudstorage/default``.
        """
        return self._post(_CLOUDSTORAGE_DEFAULT_PATH)

    def invalidate_cloud_storage(self) -> dict[str, Any]:
        """Reset (invalidate) the tenant's Cloud Storage data.

        Maps to ``POST /api/v2/rbi/cloudstorage/invalidate``.
        """
        return self._post(_CLOUDSTORAGE_INVALIDATE_PATH)

    # -- CDR (Content Disarm & Reconstruction) -----------------------------

    def get_cdr(self) -> dict[str, Any]:
        """Get the CDR configuration.

        Maps to ``GET /api/v2/rbi/cdr``.
        """
        return self._get(_CDR_PATH)

    def update_cdr(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update the CDR configuration (partial update).

        Maps to ``PATCH /api/v2/rbi/cdr``.
        """
        return self._patch(_CDR_PATH, json=config)

    def restore_cdr(self) -> dict[str, Any]:
        """Restore the CDR configuration to default values.

        Maps to ``POST /api/v2/rbi/cdr/default``.
        """
        return self._post(_CDR_DEFAULT_PATH)

    def list_cdr_vendors(self) -> dict[str, Any]:
        """List available CDR vendors and their regional endpoints.

        Maps to ``GET /api/v2/rbi/cdr/vendors``.
        """
        return self._get(_CDR_VENDORS_PATH)

    def test_cdr_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Test a candidate CDR configuration against the vendor (no persist).

        Maps to ``POST /api/v2/rbi/cdr/testconfig``.  Inspect
        ``test_result.success`` in the response for the vendor outcome.
        """
        return self._post(_CDR_TESTCONFIG_PATH, json=config)


class AsyncRbiResource(AsyncResource):
    """Asynchronous interface to the Remote Browser Isolation API."""

    # -- Reference data ----------------------------------------------------

    async def list_applications(self) -> dict[str, Any]:
        """List application names and account types RBI supports.

        See :meth:`RbiResource.list_applications`.
        """
        return await self._get(_APPLICATIONS_PATH)

    async def list_supported_browsers(self) -> dict[str, Any]:
        """List the browsers supported for isolated rendering."""
        return await self._get(_BROWSERS_PATH)

    async def list_default_categories(self) -> dict[str, Any]:
        """List the URL categories that are isolated by default."""
        return await self._get(_CATEGORIES_PATH)

    # -- Templates (read) --------------------------------------------------

    async def list_templates(
        self,
        *,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        status: builtins.list[str] | None = None,
        fields: builtins.list[str] | None = None,
    ) -> dict[str, Any]:
        """List isolation templates matching the query parameters.

        See :meth:`RbiResource.list_templates`.
        """
        params = _build_templates_params(name, limit, offset, sort_by, sort_order, status, fields)
        return await self._get(_TEMPLATES_PATH, **params)

    async def get_template(self, template_id: str) -> dict[str, Any]:
        """Get a single isolation template by id."""
        return await self._get(_template_path(template_id))

    async def get_default_template(self) -> dict[str, Any]:
        """Get the contents of the default template."""
        return await self._get(_TEMPLATES_DEFAULT_PATH)

    async def list_template_diffs(self) -> dict[str, Any]:
        """Get pending changes (diffs) for all templates."""
        return await self._get(_TEMPLATES_DIFFS_PATH)

    async def get_template_diffs(self, template_id: str) -> dict[str, Any]:
        """Get pending changes (diffs) for a single template."""
        return await self._get(f"{_template_path(template_id)}/diffs")

    # -- Templates (write) -------------------------------------------------

    async def create_template(self, template_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new template (pending deploy)."""
        return await self._post(_TEMPLATES_PATH, json=template_data)

    async def update_template(
        self, template_id: str, template_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing template (pending deploy)."""
        return await self._patch(_template_path(template_id), json=template_data)

    async def delete_template(self, template_id: str) -> dict[str, Any]:
        """Delete a template (pending deploy)."""
        return await self._delete(_template_path(template_id))

    async def restore_template(self, template_id: str) -> dict[str, Any]:
        """Restore a template to the default template values (pending deploy)."""
        return await self._post(f"{_template_path(template_id)}/default")

    async def deploy_templates(
        self,
        template_ids: builtins.list[str] | None = None,
        *,
        deploy_all: bool = False,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending changes for the specified templates.

        See :meth:`RbiResource.deploy_templates`.
        """
        body = _build_deploy_body(template_ids, note)
        params: dict[str, Any] = {"all": True} if deploy_all else {}
        return await self._post(_TEMPLATES_DEPLOY_PATH, json=body, **params)

    async def revert_templates(self, template_ids: builtins.list[str]) -> dict[str, Any]:
        """Discard pending changes for the specified templates."""
        return await self._post(_TEMPLATES_REVERT_PATH, json={"template_ids": list(template_ids)})

    # -- Cloud storage -----------------------------------------------------

    async def get_cloud_storage(self) -> dict[str, Any]:
        """Get the Cloud Storage configuration."""
        return await self._get(_CLOUDSTORAGE_PATH)

    async def update_cloud_storage(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update the Cloud Storage configuration (partial update)."""
        return await self._patch(_CLOUDSTORAGE_PATH, json=config)

    async def restore_cloud_storage(self) -> dict[str, Any]:
        """Restore the Cloud Storage configuration to default values."""
        return await self._post(_CLOUDSTORAGE_DEFAULT_PATH)

    async def invalidate_cloud_storage(self) -> dict[str, Any]:
        """Reset (invalidate) the tenant's Cloud Storage data."""
        return await self._post(_CLOUDSTORAGE_INVALIDATE_PATH)

    # -- CDR (Content Disarm & Reconstruction) -----------------------------

    async def get_cdr(self) -> dict[str, Any]:
        """Get the CDR configuration."""
        return await self._get(_CDR_PATH)

    async def update_cdr(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update the CDR configuration (partial update)."""
        return await self._patch(_CDR_PATH, json=config)

    async def restore_cdr(self) -> dict[str, Any]:
        """Restore the CDR configuration to default values."""
        return await self._post(_CDR_DEFAULT_PATH)

    async def list_cdr_vendors(self) -> dict[str, Any]:
        """List available CDR vendors and their regional endpoints."""
        return await self._get(_CDR_VENDORS_PATH)

    async def test_cdr_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Test a candidate CDR configuration against the vendor (no persist)."""
        return await self._post(_CDR_TESTCONFIG_PATH, json=config)
