"""Enums for the Netskope DSPM (Data Security Posture Management) API.

The DSPM resource endpoints return heterogeneous, resource-type-specific
payloads, so :class:`~netskope.resources.dspm.DspmResource` returns raw
``dict`` bodies rather than typed models.  The only strongly-typed surface is
this module's enums, which pin the set of routable resource types and the
sort-order values accepted by ``list_resources``.
"""

from __future__ import annotations

from enum import StrEnum


class DspmResourceType(StrEnum):
    """Routable DSPM resource types for ``GET /api/v2/dspm/{resource_type}``.

    Each value is the path segment used by the DSPM gateway route.  Passing a
    value outside this set to
    :meth:`~netskope.resources.dspm.DspmResource.list_resources` raises
    :class:`~netskope.exceptions.ValidationError` before any HTTP request.
    """

    CONNECTED_DATASTORES = "connected_datastores"
    DATABASES = "databases"
    SCHEMAS = "schemas"
    TABLES = "tables"
    COLUMNS = "columns"
    SENSITIVE_DATA_TYPES = "sensitive_data_types"
    DATA_TAGS = "data_tags"
    SCANS = "scans"
    POLICY_VIOLATIONS = "policy_violations"
    ASSESSMENT_SUMMARY = "assessment_summary"
    CLASSIFICATION_COLUMNS = "classification_columns"
    SIDECAR_POOLS = "sidecar_pools"
    INFRASTRUCTURE_CONNECTIONS = "infrastructure_connections"
    INFRASTRUCTURE_PLATFORMS = "infrastructure_platforms"
    ARCHIVED_DATASTORES = "archived_datastores"
    DISCOVERED_DATASTORES = "discovered_datastores"
    DATA_TAG_CATEGORIES = "data_tag_categories"
    SENSITIVE_DATA_TYPE_CATEGORIES = "sensitive_data_type_categories"
    SUPPORTED_DATA_TYPES = "supported_data_types"
    SENSITIVITY_LEVELS = "sensitivity_levels"
    CLASSIFICATION_FILES = "classification_files"


class SortOrder(StrEnum):
    """Sort direction for DSPM ``list_resources`` (used with ``sort_by``)."""

    ASC = "asc"
    DESC = "desc"
