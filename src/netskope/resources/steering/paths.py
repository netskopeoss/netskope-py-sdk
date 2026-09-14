"""Paths and payload builders shared by the steering resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

from typing import Any

from netskope.exceptions import ValidationError

_CLIENT_CONFIG_PATH = "/api/v2/steering/globalconfig/clientconfiguration"


_SCOPE_PATHS: dict[str, str] = {
    "npa": f"{_CLIENT_CONFIG_PATH}/npa",
    "publishers": "/api/v2/steering/globalconfig/publishers",
}


_POPS_PATH = "/api/v2/steering/ipsec/pops"


_TUNNELS_PATH = "/api/v2/steering/ipsec/tunnels"


_TUNNEL_STATUSES = ("up", "down")


IPSEC_MAX_LIMIT = 100


def _scope_path(scope: str) -> str:
    path = _SCOPE_PATHS.get(scope)
    if path is None:
        raise ValidationError(
            f"Invalid scope {scope!r}. Must be one of: {', '.join(sorted(_SCOPE_PATHS))}"
        )
    return path


def _build_pops_params(
    name: str | None,
    region: str | None,
    country: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if name is not None:
        params["name"] = name
    if region is not None:
        params["region"] = region
    if country is not None:
        params["country"] = country
    return params


def _build_tunnels_params(
    status: str | None,
    site: str | None,
    pop: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if status is not None:
        normalized = status.lower()
        if normalized not in _TUNNEL_STATUSES:
            raise ValidationError(
                f"Invalid status {status!r}. Must be one of: {', '.join(_TUNNEL_STATUSES)}"
            )
        params["status"] = normalized
    if site is not None:
        params["site"] = site
    if pop is not None:
        params["pop"] = pop
    return params
