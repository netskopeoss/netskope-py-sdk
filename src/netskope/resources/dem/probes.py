"""The probes sub-namespace of dem."""

from __future__ import annotations

import builtins
import functools
from typing import Any

from netskope.core.ids import validate_id
from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.dem._shared import (
    _list_paging_params,
)
from netskope.resources.dem.decoder import (
    AsyncDemProbeResponses,
    DemProbeResponses,
)
from netskope.resources.dem.paths import (
    _APPPROBES_PATH,
    _PROBE_LIMIT_RANGE,
    _probe_create_body,
)


class DemProbesResource(SyncResource):
    """DEM application probes — ``/api/v2/dem/appprobes``."""

    @functools.cached_property
    def with_response(self) -> DemProbeResponses:
        """Inspect one completed request together with its typed result."""

        return DemProbeResponses(self._transport)

    def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured application probes.  ``limit`` is bounded to 1-1000."""
        params = _list_paging_params(limit, offset, limit_range=_PROBE_LIMIT_RANGE)
        return self._get(_APPPROBES_PATH, **params)

    def create(
        self,
        name: str,
        target: str | None = None,
        *,
        frequency: int | None = None,
        entity: dict[str, builtins.list[str]] | None = None,
        os: builtins.list[str] | None = None,
        device_classification: builtins.list[str] | None = None,
        status: int = 1,
        app_name: str | None = None,
        app_id: int | None = None,
        move: dict[str, Any] | None = None,
        protocol: str | None = None,
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an application probe.

        ``POST /api/v2/dem/appprobes`` takes the probe object itself — no
        ``data`` wrapper.  ``name``, ``frequency``, ``entity``, ``os``,
        ``device_classification`` and ``status`` are all required, along with
        exactly one of *app_name* (a predefined app) or *app_id* (a custom
        one), and a ``move`` that places the probe in the priority list.

        Args:
            name: Probe name.
            target: Retired — the schema has no target; an app probe follows
                an app named by *app_name* or *app_id*.  Supplying it raises.
            frequency: Probe interval in minutes.
            entity: ``{"user": [...], "group": [...], "ou": [...]}``.
            os: ``"windows"`` and/or ``"mac"``.
            device_classification: ``"managed"``, ``"unmanaged"`` and/or
                ``"not configured"``.
            status: ``1`` to enable the probe, ``0`` to create it disabled.
            app_name: Name of a predefined app (``appType="predefined"``).
            app_id: ID of a custom app (``appType="custom"``).
            move: ``{"operation": "top"|"bottom"|"after"|"before"[, "position": n]}``.
                Defaults to ``{"operation": "bottom"}``.
            protocol: Retired — the schema has no protocol.  Supplying it raises.
            interval: Retired — use *frequency* (minutes).  Supplying it raises.
            additional_fields: Extra top-level body fields, merged last.

        Raises:
            netskope.exceptions.ValidationError: If a retired argument is
                supplied, a required field is missing, or the app selector is
                ambiguous.
        """
        body = _probe_create_body(
            name,
            frequency=frequency,
            entity=entity,
            os=os,
            device_classification=device_classification,
            status=status,
            app_name=app_name,
            app_id=app_id,
            move=move,
            retired={"target": target, "protocol": protocol, "interval": interval},
            additional_fields=additional_fields,
        )
        return self._post(_APPPROBES_PATH, json=body)

    def get(self, probe_id: str | int) -> dict[str, Any]:
        """Get a single application probe by ID."""
        return self._get(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """Update an application probe (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    def delete(self, probe_id: str | int) -> None:
        """Delete an application probe.  Irreversible."""
        self._delete(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


class AsyncDemProbesResource(AsyncResource):
    """Async DEM application probes."""

    @functools.cached_property
    def with_response(self) -> AsyncDemProbeResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemProbeResponses(self._transport)

    async def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured application probes.  ``limit`` is bounded to 1-1000."""
        params = _list_paging_params(limit, offset, limit_range=_PROBE_LIMIT_RANGE)
        return await self._get(_APPPROBES_PATH, **params)

    async def create(
        self,
        name: str,
        target: str | None = None,
        *,
        frequency: int | None = None,
        entity: dict[str, builtins.list[str]] | None = None,
        os: builtins.list[str] | None = None,
        device_classification: builtins.list[str] | None = None,
        status: int = 1,
        app_name: str | None = None,
        app_id: int | None = None,
        move: dict[str, Any] | None = None,
        protocol: str | None = None,
        interval: int | None = None,
        additional_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemProbesResource.create`."""
        body = _probe_create_body(
            name,
            frequency=frequency,
            entity=entity,
            os=os,
            device_classification=device_classification,
            status=status,
            app_name=app_name,
            app_id=app_id,
            move=move,
            retired={"target": target, "protocol": protocol, "interval": interval},
            additional_fields=additional_fields,
        )
        return await self._post(_APPPROBES_PATH, json=body)

    async def get(self, probe_id: str | int) -> dict[str, Any]:
        """See :meth:`DemProbesResource.get`."""
        return await self._get(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    async def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemProbesResource.update`."""
        return await self._put(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    async def delete(self, probe_id: str | int) -> None:
        """See :meth:`DemProbesResource.delete`."""
        await self._delete(f"{_APPPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")
