"""Helpers shared by the dem sub-namespaces."""

from __future__ import annotations

import builtins
from typing import Any

from netskope.core.ids import extract_list
from netskope.models.dem import (
    AdemApplication,
)
from netskope.resources.dem.paths import (
    _bounded,
)


def _list_paging_params(
    limit: int | None,
    offset: int | None,
    *,
    limit_range: tuple[int, int | None],
) -> dict[str, Any]:
    """Build a bounded ``limit``/``offset`` query for the DEM config lists."""
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = _bounded("limit", limit, *limit_range)
    if offset is not None:
        params["offset"] = _bounded("offset", offset, 0, None)
    return params


def _normalize_device_list(body: Any) -> builtins.list[dict[str, Any]]:
    """Normalize a getlist response: bare list vs ``{"data": [...]}`` / ``{"devices": [...]}``."""
    if isinstance(body, list):
        return [d for d in body if isinstance(d, dict)]
    return extract_list(body, "devices")


def _filter_apps(
    apps: builtins.list[AdemApplication] | None, application: str | None
) -> builtins.list[AdemApplication] | None:
    if apps is None or not application:
        return apps
    needle = application.lower()
    return [a for a in apps if needle in (a.app_name or "").lower()]


def _npa_host_ips(hosts: dict[str, Any] | None) -> builtins.list[str]:
    if not isinstance(hosts, dict):
        return []
    host_list = hosts.get("npaHosts")
    if not isinstance(host_list, list):
        data = hosts.get("data")
        host_list = data if isinstance(data, list) else []
    ips = []
    for h in host_list:
        if isinstance(h, dict) and h.get("npaHost"):
            ips.append(h["npaHost"])
    return ips
