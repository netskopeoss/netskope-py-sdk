"""The namespace sub-namespace of dem."""

from __future__ import annotations

import functools

from netskope.core.resource import AsyncResource, SyncResource
from netskope.resources.dem.alert_rules import (
    AsyncDemAlertRulesResource,
    DemAlertRulesResource,
)
from netskope.resources.dem.alerts import (
    AsyncDemAlertsResource,
    DemAlertsResource,
)
from netskope.resources.dem.apps import (
    AsyncDemAppsResource,
    DemAppsResource,
)
from netskope.resources.dem.network_probes import (
    AsyncDemNetworkProbesResource,
    DemNetworkProbesResource,
)
from netskope.resources.dem.probes import (
    AsyncDemProbesResource,
    DemProbesResource,
)
from netskope.resources.dem.query import (
    AsyncDemQueryResource,
    DemQueryResource,
)
from netskope.resources.dem.users import (
    AsyncDemUsersResource,
    DemUsersResource,
)


class DemResource(SyncResource):
    """Top-level DEM namespace: ``client.dem.<sub-resource>``."""

    @functools.cached_property
    def probes(self) -> DemProbesResource:
        """Application probes."""
        return DemProbesResource(self._transport)

    @functools.cached_property
    def network_probes(self) -> DemNetworkProbesResource:
        """Network probes."""
        return DemNetworkProbesResource(self._transport)

    @functools.cached_property
    def alert_rules(self) -> DemAlertRulesResource:
        """Experience-alert rules."""
        return DemAlertRulesResource(self._transport)

    @functools.cached_property
    def alerts(self) -> DemAlertsResource:
        """Triggered experience alerts."""
        return DemAlertsResource(self._transport)

    @functools.cached_property
    def query(self) -> DemQueryResource:
        """Privileged metric/entity/state/traceroute query surface."""
        return DemQueryResource(self._transport)

    @functools.cached_property
    def apps(self) -> DemAppsResource:
        """DEM-monitored applications."""
        return DemAppsResource(self._transport)

    @functools.cached_property
    def users(self) -> DemUsersResource:
        """ADEM per-user/per-device telemetry."""
        return DemUsersResource(self._transport)


class AsyncDemResource(AsyncResource):
    """Async top-level DEM namespace."""

    @functools.cached_property
    def probes(self) -> AsyncDemProbesResource:
        """Application probes."""
        return AsyncDemProbesResource(self._transport)

    @functools.cached_property
    def network_probes(self) -> AsyncDemNetworkProbesResource:
        """Network probes."""
        return AsyncDemNetworkProbesResource(self._transport)

    @functools.cached_property
    def alert_rules(self) -> AsyncDemAlertRulesResource:
        """Experience-alert rules."""
        return AsyncDemAlertRulesResource(self._transport)

    @functools.cached_property
    def alerts(self) -> AsyncDemAlertsResource:
        """Triggered experience alerts."""
        return AsyncDemAlertsResource(self._transport)

    @functools.cached_property
    def query(self) -> AsyncDemQueryResource:
        """Privileged metric/entity/state/traceroute query surface."""
        return AsyncDemQueryResource(self._transport)

    @functools.cached_property
    def apps(self) -> AsyncDemAppsResource:
        """DEM-monitored applications."""
        return AsyncDemAppsResource(self._transport)

    @functools.cached_property
    def users(self) -> AsyncDemUsersResource:
        """ADEM per-user/per-device telemetry."""
        return AsyncDemUsersResource(self._transport)
