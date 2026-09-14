"""The query sub-namespace of dem."""

from __future__ import annotations

import builtins
import functools
from datetime import datetime
from typing import Any

from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.dem import (
    DemQueryResult,
)
from netskope.resources.dem.decoder import (
    AsyncDemQueryResponses,
    DemQueryResponses,
)
from netskope.resources.dem.paths import (
    _QUERY_DEFINITIONS_PATH,
    _QUERY_GETDATA_PATH,
    _QUERY_GETENTITIES_PATH,
    _QUERY_GETSTATES_PATH,
    _QUERY_GETTRACEROUTE_PATH,
    _getdata_body,
    _getentities_body,
    _getentities_params,
    _getstates_body,
    _gettraceroute_body,
)


class DemQueryResource(SyncResource):
    """DEM metric/entity/state/traceroute query surface.

    PRIVILEGED: these endpoints are internal and are not part of the public,
    documented API.  Scoped API tokens may receive HTTP 403.
    """

    def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DemQueryResult:
        """Query one bounded dataset result, in native epoch milliseconds.

        RUM, HTTP and traceroute sources only, over a window of at most two
        days; ``limit`` accepts 0-9999 and ``offset`` 0-99999.  Sampling
        metadata is retained and does not imply complete coverage.
        """
        response = self.with_response.get_dataset(
            data_source,
            select,
            begin=begin,
            end=end,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return response.parse()

    @functools.cached_property
    def with_response(self) -> DemQueryResponses:
        """Inspect one completed request together with its typed result."""

        return DemQueryResponses(self._transport)

    def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Query experience metrics (``getdata``).  ``begin``/``end`` are epoch **ms**."""
        body = _getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return self._post(_QUERY_GETDATA_PATH, json=body, retry_safe=True)

    def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        user_location: builtins.list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """List user/device entities (``getentities``).

        ``start_time``/``end_time`` are epoch **seconds**; the operation
        declares no window cap, so the gateway decides.  ``limit`` (0-100),
        ``offset`` (0-99999), ``sort_by`` (API default ``user_score``) and
        ``sort_order`` (``asc``/``desc``) are sent as query parameters; all
        other filters, ``user_location`` included, go in the JSON body as
        ``userLocation`` (``[{"city": ..., "country": ..., "region": ...}]``).
        """
        body = _getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
            user_location,
        )
        params = _getentities_params(limit, offset, sort_order, sort_by)
        return self._post(_QUERY_GETENTITIES_PATH, json=body, retry_safe=True, **params)

    def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Query current agent/client states (``getstates``).  No time window."""
        body = _getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return self._post(_QUERY_GETSTATES_PATH, json=body, retry_safe=True)

    def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> dict[str, Any]:
        """Query traceroute path data (``gettraceroute``).  ``begin``/``end`` epoch **ms**.

        Note: this endpoint does not support a ``limit`` parameter.
        """
        body = _gettraceroute_body(data_source, begin, end, where, order_by)
        return self._post(_QUERY_GETTRACEROUTE_PATH, json=body, retry_safe=True)

    def definitions(self, *, source: str | None = None) -> dict[str, Any]:
        """List DEM field definitions for query building (``definitions``)."""
        params: dict[str, Any] = {}
        if source:
            params["source"] = source
        return self._get(_QUERY_DEFINITIONS_PATH, **params)


class AsyncDemQueryResource(AsyncResource):
    """Async DEM query surface.  PRIVILEGED — scoped tokens may 403."""

    async def get_dataset(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DemQueryResult:
        """Query one bounded dataset result, in native epoch milliseconds.

        RUM, HTTP and traceroute sources only, over a window of at most two
        days; ``limit`` accepts 0-9999 and ``offset`` 0-99999.  Sampling
        metadata is retained and does not imply complete coverage.
        """
        response = await self.with_response.get_dataset(
            data_source,
            select,
            begin=begin,
            end=end,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return response.parse()

    @functools.cached_property
    def with_response(self) -> AsyncDemQueryResponses:
        """Inspect one completed request together with its typed result."""

        return AsyncDemQueryResponses(self._transport)

    async def get_data(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_data`."""
        body = _getdata_body(
            data_source, select, begin, end, where, group_by, order_by, limit, offset
        )
        return await self._post(_QUERY_GETDATA_PATH, json=body, retry_safe=True)

    async def get_entities(
        self,
        *,
        start_time: datetime | int,
        end_time: datetime | int,
        user: str | None = None,
        application: str | None = None,
        applications: builtins.list[str] | None = None,
        device_os: builtins.list[str] | None = None,
        monitoring: str | None = None,
        exp_score: builtins.list[str] | None = None,
        pop: builtins.list[str] | None = None,
        source_ip: str | None = None,
        user_location: builtins.list[dict[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_entities`."""
        body = _getentities_body(
            start_time,
            end_time,
            user,
            application,
            applications,
            device_os,
            monitoring,
            exp_score,
            pop,
            source_ip,
            user_location,
        )
        params = _getentities_params(limit, offset, sort_order, sort_by)
        return await self._post(_QUERY_GETENTITIES_PATH, json=body, retry_safe=True, **params)

    async def get_states(
        self,
        data_source: str,
        select: builtins.list[Any],
        *,
        where: Any | None = None,
        group_by: builtins.list[str] | None = None,
        order_by: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_states`."""
        body = _getstates_body(data_source, select, where, group_by, order_by, limit, offset)
        return await self._post(_QUERY_GETSTATES_PATH, json=body, retry_safe=True)

    async def get_traceroute(
        self,
        data_source: str,
        *,
        begin: datetime | int,
        end: datetime | int,
        where: Any | None = None,
        order_by: Any | None = None,
    ) -> dict[str, Any]:
        """See :meth:`DemQueryResource.get_traceroute`."""
        body = _gettraceroute_body(data_source, begin, end, where, order_by)
        return await self._post(_QUERY_GETTRACEROUTE_PATH, json=body, retry_safe=True)

    async def definitions(self, *, source: str | None = None) -> dict[str, Any]:
        """See :meth:`DemQueryResource.definitions`."""
        params: dict[str, Any] = {}
        if source:
            params["source"] = source
        return await self._get(_QUERY_DEFINITIONS_PATH, **params)
