"""Client entry points — the main interface to the Netskope SDK.

Example::

    from netskope import NetskopeClient

    client = NetskopeClient(
        tenant="mycompany.goskope.com",
        api_token="v2-token-here",
    )

    for alert in client.alerts.list(query='severity eq "high"'):
        print(alert.alert_name)
"""

from __future__ import annotations

from typing import Any

from netskope._config import NetskopeConfig
from netskope._transport import AsyncTransport, SyncTransport
from netskope._version import __version__
from netskope.resources.alerts import AlertsResource, AsyncAlertsResource
from netskope.resources.atp import AsyncAtpResource, AtpResource
from netskope.resources.cci import AsyncCciResource, CciResource
from netskope.resources.dem import AsyncDemResource, DemResource
from netskope.resources.devices import AsyncDevicesResource, DevicesResource
from netskope.resources.dns import AsyncDnsResource, DnsResource
from netskope.resources.dspm import AsyncDspmResource, DspmResource
from netskope.resources.enrollment import AsyncEnrollmentResource, EnrollmentResource
from netskope.resources.events import AsyncEventsResource, EventsResource
from netskope.resources.incidents import AsyncIncidentsResource, IncidentsResource
from netskope.resources.ips import AsyncIpsResource, IpsResource
from netskope.resources.notifications import AsyncNotificationsResource, NotificationsResource
from netskope.resources.npa import AsyncNpaResource, NpaResource
from netskope.resources.nsiq import AsyncNsiqResource, NsiqResource
from netskope.resources.private_apps import AsyncPrivateAppsResource, PrivateAppsResource
from netskope.resources.publishers import AsyncPublishersResource, PublishersResource
from netskope.resources.rbac import AsyncRbacResource, RbacResource
from netskope.resources.rbi import AsyncRbiResource, RbiResource
from netskope.resources.scim import AsyncScimResource, ScimResource
from netskope.resources.spm import AsyncSpmResource, SpmResource
from netskope.resources.steering import AsyncSteeringResource, SteeringResource
from netskope.resources.tokens import AsyncTokensResource, TokensResource
from netskope.resources.url_lists import AsyncUrlListsResource, UrlListsResource
from netskope.resources.users import AsyncUsersResource, UsersResource


class NetskopeClient:
    """Synchronous Netskope API client.

    The primary entry point for interacting with the Netskope REST API v2.
    All API resources are accessed through hierarchical namespaces::

        client = NetskopeClient(tenant="demo.goskope.com", api_token="...")

        # Alerts
        client.alerts.list()
        client.alerts.get("abc-123")

        # Events
        client.events.list("network")

        # URL Lists
        client.url_lists.list()
        client.url_lists.create("blocklist", ["bad.com"])

        # Publishers
        client.publishers.list()

        # Private Apps
        client.private_apps.list()

        # SCIM
        client.scim.users.list()
        client.scim.groups.list()

        # Incidents
        client.incidents.list()

        # Steering & Infrastructure
        client.steering.get_config("npa")
        client.steering.list_pops()

        # NPA Policy & Infrastructure
        client.npa.policy.rules.list()
        client.npa.policy.groups.list()
        client.npa.upgrade_profiles.list()
        client.npa.local_brokers.list()

        # Devices & Enrollment
        client.devices.tags.list()
        client.enrollment.list_token_sets()

        # Identity & Access
        client.rbac.roles.list()
        client.users.list()
        client.tokens.list()
        client.notifications.list_templates()
        client.ips.status()

        # DEM / ADEM
        client.dem.probes.list()
        client.dem.users.info("alice@example.com", start_time=..., end_time=...)

        # Security services
        client.atp.scan_url("http://example.com")
        client.nsiq.url_lookup("http://example.com")
        client.rbi.list_templates()
        client.dspm.list_resources("databases")
        client.spm.list_apps()

        # DNS Profiles
        client.dns.list()

        # CCI (Cloud Confidence Index)
        client.cci.lookup_app("Dropbox")

    Args:
        tenant: The Netskope tenant hostname (e.g. ``"mycompany.goskope.com"``).
            Falls back to ``NETSKOPE_TENANT`` env var.
        api_token: A REST API v2 token. Falls back to ``NETSKOPE_API_TOKEN``.
        timeout: HTTP request timeout in seconds (default 30).
        max_retries: Max automatic retries for transient errors (default 3).
        backoff_factor: Exponential backoff multiplier (default 0.5).
        retry_on_status: HTTP status codes that trigger retries.
        verify: TLS verification — ``True`` (default), ``False`` to disable,
            or a path to a CA bundle file (see
            :func:`netskope.find_netskope_ca_cert`). Falls back to the
            ``NETSKOPE_CA_BUNDLE``, ``REQUESTS_CA_BUNDLE``, ``SSL_CERT_FILE``,
            or ``CURL_CA_BUNDLE`` env vars.
    """

    def __init__(
        self,
        tenant: str | None = None,
        api_token: str | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        retry_on_status: frozenset[int] | None = None,
        verify: bool | str = True,
    ) -> None:
        self._config = NetskopeConfig.resolve(
            tenant=tenant,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            retry_on_status=retry_on_status,
            verify=verify,
        )
        self._transport = SyncTransport(self._config)

        # Initialize resource namespaces
        self.alerts = AlertsResource(self._transport)
        self.events = EventsResource(self._transport)
        self.url_lists = UrlListsResource(self._transport)
        self.publishers = PublishersResource(self._transport)
        self.private_apps = PrivateAppsResource(self._transport)
        self.scim = ScimResource(self._transport)
        self.incidents = IncidentsResource(self._transport)
        self.steering = SteeringResource(self._transport)
        self.npa = NpaResource(self._transport)
        self.dns = DnsResource(self._transport)
        self.cci = CciResource(self._transport)
        self.devices = DevicesResource(self._transport)
        self.enrollment = EnrollmentResource(self._transport)
        self.rbac = RbacResource(self._transport)
        self.users = UsersResource(self._transport)
        self.tokens = TokensResource(self._transport)
        self.notifications = NotificationsResource(self._transport)
        self.ips = IpsResource(self._transport)
        self.dem = DemResource(self._transport)
        self.atp = AtpResource(self._transport)
        self.nsiq = NsiqResource(self._transport)
        self.rbi = RbiResource(self._transport)
        self.dspm = DspmResource(self._transport)
        self.spm = SpmResource(self._transport)

    @property
    def version(self) -> str:
        """The SDK version string."""
        return __version__

    @property
    def tenant(self) -> str:
        """The configured tenant hostname."""
        return self._config.tenant

    @property
    def base_url(self) -> str:
        """The fully-qualified API base URL."""
        return self._config.base_url

    def close(self) -> None:
        """Close the underlying HTTP connection pool.

        It is good practice to call this when you are done, or use the
        client as a context manager::

            with NetskopeClient(...) as client:
                ...
        """
        self._transport.close()

    def __enter__(self) -> NetskopeClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"NetskopeClient(tenant={self._config.tenant!r})"


class AsyncNetskopeClient:
    """Asynchronous Netskope API client.

    The async counterpart of :class:`NetskopeClient`. All resource methods
    are coroutines, and list operations return async iterators::

        async with AsyncNetskopeClient(tenant="demo.goskope.com", api_token="...") as client:
            async for alert in client.alerts.list():
                print(alert.alert_name)

    Args:
        tenant: The Netskope tenant hostname.
        api_token: A REST API v2 token.
        timeout: HTTP request timeout in seconds.
        max_retries: Max automatic retries.
        backoff_factor: Exponential backoff multiplier.
        retry_on_status: HTTP status codes that trigger retries.
        verify: TLS verification — ``True``, ``False``, or a CA bundle path.
    """

    def __init__(
        self,
        tenant: str | None = None,
        api_token: str | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        retry_on_status: frozenset[int] | None = None,
        verify: bool | str = True,
    ) -> None:
        self._config = NetskopeConfig.resolve(
            tenant=tenant,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            retry_on_status=retry_on_status,
            verify=verify,
        )
        self._transport = AsyncTransport(self._config)

        self.alerts = AsyncAlertsResource(self._transport)
        self.events = AsyncEventsResource(self._transport)
        self.url_lists = AsyncUrlListsResource(self._transport)
        self.publishers = AsyncPublishersResource(self._transport)
        self.private_apps = AsyncPrivateAppsResource(self._transport)
        self.scim = AsyncScimResource(self._transport)
        self.incidents = AsyncIncidentsResource(self._transport)
        self.steering = AsyncSteeringResource(self._transport)
        self.npa = AsyncNpaResource(self._transport)
        self.dns = AsyncDnsResource(self._transport)
        self.cci = AsyncCciResource(self._transport)
        self.devices = AsyncDevicesResource(self._transport)
        self.enrollment = AsyncEnrollmentResource(self._transport)
        self.rbac = AsyncRbacResource(self._transport)
        self.users = AsyncUsersResource(self._transport)
        self.tokens = AsyncTokensResource(self._transport)
        self.notifications = AsyncNotificationsResource(self._transport)
        self.ips = AsyncIpsResource(self._transport)
        self.dem = AsyncDemResource(self._transport)
        self.atp = AsyncAtpResource(self._transport)
        self.nsiq = AsyncNsiqResource(self._transport)
        self.rbi = AsyncRbiResource(self._transport)
        self.dspm = AsyncDspmResource(self._transport)
        self.spm = AsyncSpmResource(self._transport)

    @property
    def version(self) -> str:
        return __version__

    @property
    def tenant(self) -> str:
        return self._config.tenant

    @property
    def base_url(self) -> str:
        return self._config.base_url

    async def close(self) -> None:
        """Close the underlying async HTTP connection pool."""
        await self._transport.close()

    async def __aenter__(self) -> AsyncNetskopeClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncNetskopeClient(tenant={self._config.tenant!r})"
