"""DSPM resource models and the legacy resource-name enumeration."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from netskope.models.common import NetskopeModel


class DspmResourceType(StrEnum):
    """Legacy resource names, retained for ``list_resources`` compatibility.

    The verified typed surface maps a subset to canonical public routes. Use
    ``DspmResource.supported_resource_types()`` to discover that subset.
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


class DspmRecord(NetskopeModel):
    """Common DSPM identity, with endpoint-specific subclasses below."""

    id: str | int | None = None
    name: str | None = None


class DspmDatastore(DspmRecord):
    endpoint: str | None = None
    service_id: int | None = None
    infrastructure_connection_id: str | int | None = None
    account_id: str | int | None = None
    region: str | None = None
    data_owners: list[str] | None = None
    scan_status: int | None = None
    data_store_sensitivity_score: int | None = None
    data_store_risk_rating: int | None = None
    table_count: int | None = None
    field_count: int | None = None
    database_count: int | None = None
    schema_count: int | None = None
    sensitive_field_count: int | None = None
    sensitive_record_count: int | None = None
    data_tag_ids: list[str] | None = None
    contained_data_tag_ids: list[str] | None = None
    first_found: int | None = None
    last_accessed_on: int | None = None
    unstructured_file_count: int | None = None
    unstructured_size_bytes: int | None = None
    structured_size_bytes: int | None = None
    sidecar_pool_id: str | int | None = None


class DspmDatabaseMetadata(NetskopeModel):
    row_count: int | None = None
    record_count: int | None = None
    sensitive_record_count: int | None = None
    schema_count: int | None = None
    table_count: int | None = None
    field_count: int | None = None
    sensitive_field_count: int | None = None
    structured_sensitive_data_size_bytes: int | None = None
    structured_size_bytes: int | None = None
    last_accessed_by: str | None = None
    last_accessed: int | None = None
    last_accessed_on: int | None = None
    data_size: int | None = None
    stale_data_size: int | None = None


class DspmDatabaseObject(DspmRecord):
    """A database, schema, or table in the connected-datastore inventory."""

    data_owners: list[str] | None = None
    data_tag_ids: list[str] | None = None
    inherited_data_tag_ids: list[str] | None = None
    data_store_id: int | None = None
    database_id: int | None = None
    first_seen: int | None = None
    meta_data: DspmDatabaseMetadata | None = None


class DspmColumnLocation(NetskopeModel):
    data_store_id: str | int | None = None
    database_id: str | int | None = None
    schema_id: str | int | None = None
    table_id: str | int | None = None
    column: str | None = None


class DspmColumnUsage(NetskopeModel):
    level: int | None = None
    percentile: float | None = None


class DspmClassificationColumn(DspmRecord):
    classification: int | None = None
    confidence: float | None = None
    reclassify: bool | None = None
    reviewed: bool | None = None
    location: DspmColumnLocation | None = None
    data_tag_ids: list[str] | None = None
    data_type: DspmRecord | None = None
    sensitivity_level: DspmRecord | None = None
    usage: DspmColumnUsage | None = None
    usernames: list[str] | None = None
    last_seen: int | None = None
    status: str | None = None


class DspmFileSensitiveType(NetskopeModel):
    data_tags: list[int] | None = Field(None, alias="dataTags")
    data_type: DspmRecord | None = Field(None, alias="dataType")
    occurrence_count: int | None = Field(None, alias="occurenceCount")
    sensitivity_level: DspmRecord | None = Field(None, alias="sensitivityLevel")


class DspmClassificationFile(DspmRecord):
    file_name: str | None = Field(None, alias="fileName")
    data_store: str | None = Field(None, alias="dataStore")
    data_store_id: str | int | None = Field(None, alias="dataStoreId")
    sensitive_data_types: list[DspmFileSensitiveType] | None = Field(
        None, alias="sensitiveDataTypes"
    )


class DspmCategory(DspmRecord):
    description: str | None = None
    is_system_created: bool | None = None
    is_enabled: bool | None = None


class DspmDataTag(DspmCategory):
    category_id: str | int | None = None
    color: str | None = None


class DspmKeywordMatch(NetskopeModel):
    type: str | None = None
    regex: str | None = None
    value: list[str] | None = None


class DspmContentMatch(NetskopeModel):
    type: str | None = None
    regex: str | None = None
    value: str | None = None


class DspmMatchConditions(NetskopeModel):
    keywords: DspmKeywordMatch | None = None
    content: DspmContentMatch | None = None


class DspmSensitiveDataType(DspmRecord):
    description: str | None = None
    category_id: str | int | None = None
    sensitivity_level_id: int | None = None
    is_masked: bool | None = None
    is_enabled: bool | None = None
    data_tag_ids: list[int] | None = None
    match_conditions: DspmMatchConditions | None = None


class DspmSidecarPool(DspmRecord):
    status: str | None = None
    data_store_count: int | None = None
    sidecar_count: int | None = None


class DspmInfrastructureConnection(DspmRecord):
    account_id: str | int | None = None
    auto_discovery_enabled: bool | None = None
    auto_connect_enabled: bool | None = None
    platform_id: int | None = None
    organization_id: str | int | None = None


class DspmScanRequest(BaseModel):
    """The verified start-scan operation addresses exactly one datastore."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: str = Field(min_length=1)
