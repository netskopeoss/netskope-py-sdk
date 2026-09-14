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
import functools
from typing import Any, cast

from netskope.core.resource import AsyncResource, SyncResource
from netskope.exceptions import ValidationError
from netskope.resources.rbi.decoder import AsyncRbiResponses, RbiResponses
from netskope.resources.rbi.paths import (
    _APPLICATIONS_PATH,
    _BROWSERS_PATH,
    _CATEGORIES_PATH,
    _RBI_PATH,
    _TEMPLATES_PATH,
    _template_path,
)

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


# ``GET /templates`` enumerates every sort, status and field value
# (rbi/templates.yaml:181-257).
_TEMPLATE_SORT_FIELDS = ("template_id", "template_name", "template_status", "modification_time")
_TEMPLATE_SORT_ORDERS = ("asc", "desc")
_TEMPLATE_STATUSES = ("applied", "pending-create", "pending-delete", "pending-update")
_TEMPLATE_FIELDS = (
    "name",
    "asterisk_prefix",
    "colored_frame",
    "popup_message",
    "file_download",
    "file_upload",
    "copy_from_isolated_page",
    "paste_into_isolated_page",
    "popups",
    "printing",
    "readonly",
    "private_navigation",
    "watermark",
)


def _as_list(name: str, value: str | builtins.list[str]) -> builtins.list[str]:
    """Accept a single value where the operation takes a list.

    A bare ``str`` is iterable, so forwarding it unchanged would serialise
    ``"applied"`` as ``a,p,p,l,i,e,d``. One value is the common case for these
    parameters, so it is accepted rather than rejected.
    """
    if isinstance(value, str):
        return [value]
    return builtins.list(value)


def _one_of(name: str, value: str, allowed: tuple[str, ...]) -> str:
    """Return *value* when the operation enumerates it, else raise."""
    if value not in allowed:
        raise ValidationError(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _all_of(name: str, values: builtins.list[str], allowed: tuple[str, ...]) -> builtins.list[str]:
    """Return *values* when every entry is enumerated, else raise."""
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ValidationError(
            f"Invalid {name} value(s): {', '.join(map(str, invalid))}. "
            f"Must be one of: {', '.join(allowed)}"
        )
    return builtins.list(values)


def _build_templates_params(
    name: str | None,
    limit: int | None,
    offset: int | None,
    sort_by: str | None,
    sort_order: str | None,
    status: str | builtins.list[str] | None,
    fields: str | builtins.list[str] | None,
) -> dict[str, Any]:
    """Build the query params for ``GET /rbi/templates``.

    ``status`` and ``fields`` are serialized as comma-separated lists
    (OpenAPI ``style=form, explode=false``) and every value is checked against
    the declared enumeration; ``status`` also declares ``minItems: 1``
    (rbi/templates.yaml:220-229).
    """
    params: dict[str, Any] = {}
    if name is not None:
        params["name"] = name
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if sort_by is not None:
        params["sortby"] = _one_of("sort_by", sort_by, _TEMPLATE_SORT_FIELDS)
    if sort_order is not None:
        params["sortorder"] = _one_of("sort_order", sort_order, _TEMPLATE_SORT_ORDERS)
    if status is not None:
        if not status:
            raise ValidationError("status must name at least one template status.")
        params["status"] = ",".join(
            _all_of("status", _as_list("status", status), _TEMPLATE_STATUSES)
        )
    if fields is not None:
        params["fields"] = ",".join(_all_of("fields", _as_list("fields", fields), _TEMPLATE_FIELDS))
    return params


def _build_deploy_body(
    template_ids: str | builtins.list[str] | None,
    note: str | None,
) -> dict[str, Any] | None:
    """Build the deploy body; ``template_ids`` declares minItems 1.

    rbi/templates.yaml:2061 and :2085 bound the array, and :456-460 says
    ``all=true`` and an explicit id list are mutually exclusive.
    """
    body: dict[str, Any] = {}
    if template_ids is not None:
        ids = _as_list("template_ids", template_ids)
        if not ids:
            raise ValidationError("template_ids must name at least one template.")
        body["template_ids"] = ids
    if note is not None:
        body["note"] = note
    return body or None


# ``GET /cdr/testconfig`` query parameters (rbi/cdr.yaml:424-471).
_CDR_TESTCONFIG_QUERY = ("vendor", "id", "endpoint_url", "workflow_rule_name")
# Inline mode carries the key in the ``X-CDR-Api-Key`` header (cdr.yaml:472-480).
_CDR_TESTCONFIG_API_KEY_KEYS = frozenset({"api_key", "apikey", "x-cdr-api-key", "x_cdr_api_key"})


def _build_cdr_testconfig_params(
    config: dict[str, Any] | None,
    vendor: str | None,
    config_id: str | None,
    endpoint_url: str | None,
    workflow_rule_name: str | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build the ``GET /cdr/testconfig`` query and its headers.

    *config* is the legacy body-shaped argument; its ``vendor``/``id``/
    ``endpoint_url``/``workflow_rule_name`` entries become query parameters.

    An inline API key (``api_key``) travels in the ``X-CDR-Api-Key`` header
    (cdr.yaml:472-480), never in the query string.

    Raises:
        netskope.exceptions.ValidationError: If *config* names a field the
            operation does not declare, or nothing selects a configuration.
    """
    merged: dict[str, Any] = {}
    headers: dict[str, str] = {}
    if config is not None:
        if not isinstance(config, dict):
            raise ValidationError("test_cdr_config takes a mapping of query values.")
        for key, value in config.items():
            if str(key).lower() in _CDR_TESTCONFIG_API_KEY_KEYS:
                if value:
                    headers["X-CDR-Api-Key"] = str(value)
                continue
            if key not in _CDR_TESTCONFIG_QUERY:
                raise ValidationError(
                    f"GET /rbi/cdr/testconfig does not accept {key!r}. "
                    f"Supported: {', '.join(_CDR_TESTCONFIG_QUERY)}."
                )
            if value is not None:
                merged[key] = value
    for key, value in (
        ("vendor", vendor),
        ("id", config_id),
        ("endpoint_url", endpoint_url),
        ("workflow_rule_name", workflow_rule_name),
    ):
        if value is not None:
            merged[key] = value
    if not merged:
        raise ValidationError(
            "A CDR connectivity test needs either config_id=<stored config id>, or the "
            "inline vendor, endpoint_url and workflow_rule_name."
        )
    return merged, headers


class RbiResource(SyncResource):
    """Synchronous interface to the Remote Browser Isolation API."""

    @functools.cached_property
    def with_response(self) -> RbiResponses:

        return RbiResponses(self._transport)

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
        status: str | builtins.list[str] | None = None,
        fields: str | builtins.list[str] | None = None,
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

    def get_template(self, template_id: int | str) -> dict[str, Any]:
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

    def get_template_diffs(self, template_id: int | str) -> dict[str, Any]:
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

    def update_template(
        self, template_id: int | str, template_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing template (pending deploy).

        Maps to ``PATCH /api/v2/rbi/templates/{id}``.  Accepts a partial
        ``TemplatePatchData`` body; at least one supported field is required.
        """
        return self._patch(_template_path(template_id), json=template_data)

    def delete_template(self, template_id: int | str) -> dict[str, Any]:
        """Delete a template (pending deploy).

        Maps to ``DELETE /api/v2/rbi/templates/{id}``.
        """
        return self._delete(_template_path(template_id))

    def restore_template(self, template_id: int | str) -> dict[str, Any]:
        """Restore a template to the default template values (pending deploy).

        Maps to ``POST /api/v2/rbi/templates/{id}/default``.
        """
        return self._post(f"{_template_path(template_id)}/default")

    def deploy_templates(
        self,
        template_ids: str | builtins.list[str] | None = None,
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
        if deploy_all and template_ids is not None:
            raise ValidationError(
                "Provide exactly one of template_ids or deploy_all=True "
                "(rbi/templates.yaml:456-460)."
            )
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
        """Reset the CDR configuration to factory defaults.

        Maps to ``PUT /api/v2/rbi/cdr/default`` (``RestoreCdr``).  Destructive:
        it empties ``cdr_data`` and clears ``active_vendor``, and fails with
        HTTP 409 while a vendor config is still referenced by a template.
        """
        return self._put(_CDR_DEFAULT_PATH)

    def list_cdr_vendors(self) -> dict[str, Any]:
        """List available CDR vendors and their regional endpoints.

        Maps to ``GET /api/v2/rbi/cdr/vendors``.
        """
        return self._get(_CDR_VENDORS_PATH)

    def test_cdr_config(
        self,
        config: dict[str, Any] | None = None,
        *,
        vendor: str | None = None,
        config_id: str | None = None,
        endpoint_url: str | None = None,
        workflow_rule_name: str | None = None,
    ) -> dict[str, Any]:
        """Test CDR vendor connectivity without persisting anything.

        Maps to ``GET /api/v2/rbi/cdr/testconfig`` (``TestCdrConfig``); the
        settings travel as query parameters, not as a request body.  Inspect
        ``test_result.success`` in the response for the vendor outcome.

        Inline mode sends the raw key in the ``X-CDR-Api-Key`` request header;
        pass it as ``config={"api_key": ...}`` alongside the vendor settings.

        Args:
            config: Legacy mapping form; its ``vendor``, ``id``,
                ``endpoint_url`` and ``workflow_rule_name`` entries become
                query parameters.
            vendor: Vendor name (inline mode; resolved from the stored config
                when *config_id* is given).
            config_id: ID of a stored vendor config entry — sent as ``id``.
            endpoint_url: Vendor endpoint URL (inline mode).
            workflow_rule_name: Workflow/rule name to exercise during the test.

        Raises:
            netskope.exceptions.ValidationError: If no selector is supplied or an
                unsupported key is passed.
        """
        params, headers = _build_cdr_testconfig_params(
            config, vendor, config_id, endpoint_url, workflow_rule_name
        )
        response = self._transport.request(
            "GET", _CDR_TESTCONFIG_PATH, params=params or None, headers=headers or None
        )
        return cast(dict[str, Any], response.json())


class AsyncRbiResource(AsyncResource):
    """Asynchronous interface to the Remote Browser Isolation API."""

    @functools.cached_property
    def with_response(self) -> AsyncRbiResponses:

        return AsyncRbiResponses(self._transport)

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
        status: str | builtins.list[str] | None = None,
        fields: str | builtins.list[str] | None = None,
    ) -> dict[str, Any]:
        """List isolation templates matching the query parameters.

        See :meth:`RbiResource.list_templates`.
        """
        params = _build_templates_params(name, limit, offset, sort_by, sort_order, status, fields)
        return await self._get(_TEMPLATES_PATH, **params)

    async def get_template(self, template_id: int | str) -> dict[str, Any]:
        """Get a single isolation template by id."""
        return await self._get(_template_path(template_id))

    async def get_default_template(self) -> dict[str, Any]:
        """Get the contents of the default template."""
        return await self._get(_TEMPLATES_DEFAULT_PATH)

    async def list_template_diffs(self) -> dict[str, Any]:
        """Get pending changes (diffs) for all templates."""
        return await self._get(_TEMPLATES_DIFFS_PATH)

    async def get_template_diffs(self, template_id: int | str) -> dict[str, Any]:
        """Get pending changes (diffs) for a single template."""
        return await self._get(f"{_template_path(template_id)}/diffs")

    # -- Templates (write) -------------------------------------------------

    async def create_template(self, template_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new template (pending deploy)."""
        return await self._post(_TEMPLATES_PATH, json=template_data)

    async def update_template(
        self, template_id: int | str, template_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing template (pending deploy)."""
        return await self._patch(_template_path(template_id), json=template_data)

    async def delete_template(self, template_id: int | str) -> dict[str, Any]:
        """Delete a template (pending deploy)."""
        return await self._delete(_template_path(template_id))

    async def restore_template(self, template_id: int | str) -> dict[str, Any]:
        """Restore a template to the default template values (pending deploy)."""
        return await self._post(f"{_template_path(template_id)}/default")

    async def deploy_templates(
        self,
        template_ids: str | builtins.list[str] | None = None,
        *,
        deploy_all: bool = False,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Deploy pending changes for the specified templates.

        See :meth:`RbiResource.deploy_templates`.
        """
        if deploy_all and template_ids is not None:
            raise ValidationError(
                "Provide exactly one of template_ids or deploy_all=True "
                "(rbi/templates.yaml:456-460)."
            )
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
        """Reset the CDR configuration to factory defaults.

        See :meth:`RbiResource.restore_cdr`.
        """
        return await self._put(_CDR_DEFAULT_PATH)

    async def list_cdr_vendors(self) -> dict[str, Any]:
        """List available CDR vendors and their regional endpoints."""
        return await self._get(_CDR_VENDORS_PATH)

    async def test_cdr_config(
        self,
        config: dict[str, Any] | None = None,
        *,
        vendor: str | None = None,
        config_id: str | None = None,
        endpoint_url: str | None = None,
        workflow_rule_name: str | None = None,
    ) -> dict[str, Any]:
        """Test CDR vendor connectivity without persisting anything.

        See :meth:`RbiResource.test_cdr_config`.
        """
        params, headers = _build_cdr_testconfig_params(
            config, vendor, config_id, endpoint_url, workflow_rule_name
        )
        response = await self._transport.request(
            "GET", _CDR_TESTCONFIG_PATH, params=params or None, headers=headers or None
        )
        return cast(dict[str, Any], response.json())
