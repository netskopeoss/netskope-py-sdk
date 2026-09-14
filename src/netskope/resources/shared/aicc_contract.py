"""Operation capabilities from the pinned AICC gateway contract.

Derived from a pinned revision of the Netskope API gateway contract for the
AICC inventory endpoints; the contract definitions are not public.
"""

from __future__ import annotations

# Reusable enumerations shared by several operations.
# ``ReconciledRiskLevel`` (aicc/inventory.yaml:6851-6853).
_RISK_LEVELS = ("Critical", "High", "Medium", "Low", "Inconclusive", "Legitimate", "Unknown")
# Extension subtypes (aicc/inventory.yaml:1521-1531).
_EXTENSION_TYPES = ("browser_extension", "editor_extension", "desktop_extension")
# Model deployment shapes (aicc/inventory.yaml:3902-3914).
_MODEL_DEPLOYMENTS = ("cloud", "endpoint", "self_hosted_vm", "self_hosted_k8s")
# Data-protection violation severities (aicc/inventory.yaml:3752-3763).
_VIOLATION_SEVERITIES = ("critical", "high", "medium", "low")

# Query name, required flag, maximum page size, enum values. A parameter the
# gateway types as an array is checked element by element.
QUERY_RULES: dict[str, tuple[tuple[str, bool, int | None, tuple[str, ...]], ...]] = {
    "/analytics/counts": (
        (
            "type",
            True,
            None,
            (
                "identities",
                "assets",
                "alerts",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/analytics/sums": (
        (
            "type",
            True,
            None,
            (
                "traffic",
                "sessions",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/analytics/entity-counts": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("active_only", False, None, ()),
    ),
    "/data-coverage": (),
    "/analytics/ai-applications": (
        (
            "dimension",
            True,
            None,
            (
                "category",
                "status",
                "ccl",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        (
            "metric",
            False,
            None,
            (
                "count",
                "bytes",
                "sessions",
                "transactions",
            ),
        ),
        ("category", False, None, ()),
        ("status", False, None, ()),
        ("ccl", False, None, ()),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("active_only", False, None, ()),
    ),
    "/analytics/mcp-servers": (
        (
            "dimension",
            True,
            None,
            (
                "category",
                "ccl",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        (
            "metric",
            False,
            None,
            (
                "count",
                "sessions",
                "transactions",
            ),
        ),
        ("category", False, None, ()),
        ("auth_method", False, None, ()),
        ("ccl", False, None, ()),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("active_only", False, None, ()),
    ),
    "/analytics/identities": (
        (
            "dimension",
            True,
            None,
            (
                "user_group",
                "ou",
                "activity_level",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        (
            "metric",
            False,
            None,
            (
                "count",
                "bytes",
                "sessions",
                "transactions",
            ),
        ),
        ("user_group", False, None, ()),
        ("ou", False, None, ()),
        ("activity_level", False, None, ()),
        (
            "type",
            False,
            None,
            (
                "user",
                "unknown",
                "nhi",
                "null",
            ),
        ),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("active_only", False, None, ()),
    ),
    "/analytics/alerts/matrix": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("detection", False, None, ()),
        (
            "asset",
            False,
            None,
            (
                "AI App",
                "MCP Server",
            ),
        ),
    ),
    "/analytics/alerts/policies": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("detection", False, None, ()),
        (
            "asset",
            False,
            None,
            (
                "AI App",
                "MCP Server",
            ),
        ),
    ),
    "/inventory/ai-applications": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("sort", False, None, ()),
        ("search", False, None, ()),
        ("category", False, None, ()),
        ("status", False, None, ()),
        ("ccl", False, None, ()),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("first_seen_after", False, None, ()),
        ("active_only", False, None, ()),
    ),
    "/inventory/mcp-servers": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("sort", False, None, ()),
        ("search", False, None, ()),
        ("category", False, None, ()),
        ("ccl", False, None, ()),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("active_only", False, None, ()),
    ),
    "/inventory/extensions/{extension_name}": (
        (
            "type",
            False,
            None,
            (
                "browser_extension",
                "editor_extension",
                "desktop_extension",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/extensions/{extension_name}/deployments": (
        (
            "type",
            True,
            None,
            (
                "browser_extension",
                "editor_extension",
                "desktop_extension",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
    ),
    "/inventory/extensions/{extension_name}/identities": (
        ("type", False, None, _EXTENSION_TYPES),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
    "/inventory/identities": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("sort", False, None, ()),
        ("search", False, None, ()),
        (
            "type",
            False,
            None,
            (
                "user",
                "unknown",
            ),
        ),
        ("user_group", False, None, ()),
        ("ou", False, None, ()),
        ("activity_level", False, None, ()),
        ("reconciled_risk_level", False, None, _RISK_LEVELS),
        ("first_seen_after", False, None, ()),
        ("active_only", False, None, ()),
    ),
    "/inventory/ai-applications/{app_name}": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/status": (
        ("start_time", False, None, ()),
        ("end_time", False, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/identities": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "events",
                "sessions",
                "uploaded_bytes",
                "downloaded_bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
        ("search", False, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/deployments": (
        (
            "type",
            True,
            None,
            (
                "cloud_web",
                "endpoint",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}/identities": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 100, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "events",
                "sessions",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
        ("search", False, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}/deployments": (
        (
            "type",
            True,
            None,
            (
                "cloud",
                "endpoint",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/identities/{identity_id}": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/traffic-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/risk-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}/traffic-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}/identity-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/mcp-servers/{server_name}/risk-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/identities/{identity_id}/traffic-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/identities/{identity_id}/risk-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/identity-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/ai-applications/{app_name}/violations": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 100, ()),
    ),
    "/inventory/mcp-servers/{server_name}/violations": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 100, ()),
        (
            "status",
            False,
            None,
            (
                "current",
                "dismissed",
            ),
        ),
    ),
    "/provider/{provider}/data-protection/summary": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/provider/{provider}/data-protection/violations": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("limit", False, 100, ()),
        ("offset", False, None, ()),
        ("severity", False, None, _VIOLATION_SEVERITIES),
        ("object_type", False, None, ()),
        ("search", False, None, ()),
        ("user", False, None, ()),
        ("include_total", False, None, ()),
    ),
    "/inventory/models": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("sort", False, None, ()),
        ("search", False, None, ()),
        ("deployment", False, None, _MODEL_DEPLOYMENTS),
        ("provider", False, None, ()),
        ("active_only", False, None, ()),
        ("first_seen_after", False, None, ()),
    ),
    "/inventory/models/{model_name}": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/models/{model_name}/identities": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
    "/inventory/models/{model_name}/traffic-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/models/{model_name}/deployments": (
        (
            "type",
            True,
            None,
            (
                "cloud",
                "endpoint",
                "self_hosted_vm",
                "self_hosted_k8s",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
    ),
    "/analytics/models": (
        (
            "dimension",
            True,
            None,
            (
                "footprint",
                "provider",
            ),
        ),
        (
            "metric",
            False,
            None,
            (
                "count",
                "bytes",
                "identities",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/agents": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("sort", False, None, ()),
        ("search", False, None, ()),
        ("category", False, None, ()),
        ("framework", False, None, ()),
        ("active_only", False, None, ()),
        ("first_seen_after", False, None, ()),
    ),
    "/inventory/agents/{agent_name}": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/agents/{agent_name}/identities": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
    "/inventory/agents/{agent_name}/traffic-trend": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("timezone", True, None, ()),
    ),
    "/inventory/agents/{agent_name}/deployments": (
        (
            "type",
            True,
            None,
            (
                "vm",
                "kubernetes",
                "endpoint",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
    ),
    "/analytics/agents": (
        (
            "dimension",
            True,
            None,
            (
                "category",
                "framework",
            ),
        ),
        (
            "metric",
            False,
            None,
            (
                "count",
                "bytes",
                "sessions",
                "identities",
            ),
        ),
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
    ),
    "/inventory/identities/{identity_id}/agents": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
    "/inventory/identities/{identity_id}/models": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
    "/inventory/identities/{identity_id}/mcp-servers": (
        ("start_time", True, None, ()),
        ("end_time", True, None, ()),
        ("offset", False, None, ()),
        ("limit", False, 200, ()),
        ("search", False, None, ()),
        (
            "sort_by",
            False,
            None,
            (
                "name",
                "bytes",
            ),
        ),
        (
            "sort_dir",
            False,
            None,
            (
                "asc",
                "desc",
            ),
        ),
    ),
}
