"""The network probes sub-namespace of dem."""

from __future__ import annotations

import functools
from typing import Any

from netskope.core.ids import validate_id
from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.dem._shared import (
    _list_paging_params,
)
from netskope.resources.dem.decoder import (
    AsyncDemNetworkProbeResponses,
    DemNetworkProbeResponses,
)
from netskope.resources.dem.paths import (
    _NETWORKPROBES_PATH,
    _PROBE_LIMIT_RANGE,
)


class DemNetworkProbesResource(SyncResource):
    """DEM network probes — ``/api/v2/dem/networkprobes``."""

    @functools.cached_property
    def with_response(self) -> DemNetworkProbeResponses:
        """Inspect one completed request together with its typed result."""

        return DemNetworkProbeResponses(self._transport)

    def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured network probes.  ``limit`` is bounded to 1-1000."""
        params = _list_paging_params(limit, offset, limit_range=_PROBE_LIMIT_RANGE)
        return self._get(_NETWORKPROBES_PATH, **params)

    def get(self, probe_id: str | int) -> dict[str, Any]:
        """Get a single network probe by ID."""
        return self._get(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """Update a network probe (PUT).  *data* is sent as the raw body."""
        return self._put(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data)

    def delete(self, probe_id: str | int) -> None:
        """Delete a network probe.  Irreversible."""
        self._delete(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")


class AsyncDemNetworkProbesResource(AsyncResource):
    """Async DEM network probes."""

    @functools.cached_property
    def with_response(self) -> AsyncDemNetworkProbeResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemNetworkProbeResponses(self._transport)

    async def list(self, *, limit: int | None = None, offset: int | None = None) -> dict[str, Any]:
        """List configured network probes.  ``limit`` is bounded to 1-1000."""
        params = _list_paging_params(limit, offset, limit_range=_PROBE_LIMIT_RANGE)
        return await self._get(_NETWORKPROBES_PATH, **params)

    async def get(self, probe_id: str | int) -> dict[str, Any]:
        """See :meth:`DemNetworkProbesResource.get`."""
        return await self._get(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")

    async def update(self, probe_id: str | int, data: dict[str, Any]) -> dict[str, Any]:
        """See :meth:`DemNetworkProbesResource.update`."""
        return await self._put(
            f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}", json=data
        )

    async def delete(self, probe_id: str | int) -> None:
        """See :meth:`DemNetworkProbesResource.delete`."""
        await self._delete(f"{_NETWORKPROBES_PATH}/{validate_id(probe_id, 'probe_id')}")
