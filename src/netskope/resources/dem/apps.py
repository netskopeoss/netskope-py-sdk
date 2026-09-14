"""The apps sub-namespace of dem."""

from __future__ import annotations

import functools
from typing import Any

from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.dem._shared import (
    _list_paging_params,
)
from netskope.resources.dem.decoder import (
    AsyncDemAppResponses,
    DemAppResponses,
)
from netskope.resources.dem.paths import (
    _APP_LIMIT_RANGE,
    _APPS_PATH,
)


class DemAppsResource(SyncResource):
    """DEM-monitored applications — ``/api/v2/dem/apps``."""

    @functools.cached_property
    def with_response(self) -> DemAppResponses:
        """Inspect one completed request together with its typed result."""

        return DemAppResponses(self._transport)

    def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DEM-monitored applications.  ``app_type`` is ``custom`` or ``predefined``.

        ``limit`` is bounded to 1 or more (demconfig.yaml:110-116).
        """
        params = _list_paging_params(limit, offset, limit_range=_APP_LIMIT_RANGE)
        if app_type:
            params["type"] = app_type
        if name:
            params["name"] = name
        return self._get(_APPS_PATH, **params)


class AsyncDemAppsResource(AsyncResource):
    """Async DEM-monitored applications."""

    @functools.cached_property
    def with_response(self) -> AsyncDemAppResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemAppResponses(self._transport)

    async def list(
        self,
        *,
        app_type: str | None = None,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """List DEM-monitored applications.  ``app_type`` is ``custom`` or ``predefined``.

        ``limit`` is bounded to 1 or more (demconfig.yaml:110-116).
        """
        params = _list_paging_params(limit, offset, limit_range=_APP_LIMIT_RANGE)
        if app_type:
            params["type"] = app_type
        if name:
            params["name"] = name
        return await self._get(_APPS_PATH, **params)
