"""Models for the Netskope Infrastructure API (tunnels, PoPs, brokers)."""

from __future__ import annotations

from enum import StrEnum
from ipaddress import IPv4Address
from typing import Any, Final, Literal, Self

from pydantic import AliasChoices, Field, field_validator, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class ReleaseType(StrEnum):
    """Publisher release channel for upgrade profiles."""

    BETA = "Beta"
    LATEST = "Latest"
    LATEST_1 = "Latest-1"
    LATEST_2 = "Latest-2"


class BrokerPublicIpAccess(StrEnum):
    """Access policy for reaching a local broker via its public IP."""

    NONE = "NONE"
    OFF_PREM = "OFF_PREM"
    ON_PREM = "ON_PREM"
    ON_OFF_PREM = "ON_OFF_PREM"


class Pop(NetskopeModel):
    """A Netskope Point of Presence (PoP) where IPsec tunnels terminate.

    Mirrors ``ipsec_pop_result_item`` (``steering/ipsec.yaml:28-81``).
    ``country`` is a *query* parameter on ``GET /ipsec/pops`` (``:408-415``),
    not a response field, and the response has no address list; use ``gateway``
    and ``probeip``.  Unmodelled keys remain reachable — the model allows
    extras.
    """

    id: str | int | None = None
    name: str | None = None
    region: str | None = None
    location: str | None = None
    gateway: str | None = None
    probeip: str | None = None
    bandwidth: str | int | None = None
    distance: str | int | None = None
    acceptingtunnels: bool | None = None
    releasedeploymentday: str | None = None
    options: dict[str, Any] | None = None


class IPSecTunnel(NetskopeModel):
    """An IPSec VPN tunnel.

    Mirrors ``ipsec_tunnel_result_item`` (``steering/ipsec.yaml:318-379``).
    The response reports ``enabled`` (``:323-325``) even though the request
    body writes ``enable``, and ``pops`` is an array of
    ``ipsec_tunnel_pop_result_item`` objects (``:355-358`` → ``:158-183``)
    rather than the array of names the request takes (``:265-269``).
    """

    id: int | None = None
    site: str | None = None
    enabled: bool | None = None
    bandwidth: int | None = None
    encryption: str | None = None
    notes: str | None = None
    pops: list[dict[str, Any]] | None = None
    sourcetype: str | None = None
    srcidentity: str | None = None
    srcipidentity: str | None = None
    template: str | None = None
    vendor: str | None = None
    version: int | None = None
    options: dict[str, Any] | None = None


class LocalBroker(NetskopeModel):
    """A Local Broker for publisher connectivity.

    Mirrors ``lbroker_response.data`` (``npa_lbrokers.yaml:139-183``) and the
    list item (``:192-242``); neither declares a status or an owning publisher.
    """

    id: int | None = None
    name: str | None = None
    common_name: str | None = None
    registered: bool | None = None
    city_name: str | None = None
    region_name: str | None = None
    country_name: str | None = None
    country_code: str | None = None
    location_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    discovered_public_ip: str | None = None
    discovered_private_ip: str | None = None
    custom_public_ip: str | None = None
    custom_private_ip: str | None = None
    labels: list[dict[str, Any]] = Field(default_factory=list)


class LocalBrokerConfig(NetskopeModel):
    """Tenant-wide local broker configuration."""

    hostname: str | None = None


class PublisherUpgradeProfile(NetskopeModel):
    """A publisher upgrade profile.

    ``publisher_upgrade_profile_response.data``
    (``npa_upgrade_profiles.yaml:656-709``) — the body of both ``POST
    /publisherupgradeprofiles`` and ``PUT /publisherupgradeprofiles/{external_id}``
    — carries the external id under ``id`` and has no ``external_id`` key,
    while the get-by-id response (``:206-272``) and list item (``:279-350``)
    carry both.  ``external_id`` reads whichever the response provides, so a
    freshly created profile can be passed straight to
    :meth:`~netskope.resources.upgrade_profiles.UpgradeProfilesResource.assign`.
    """

    id: int | None = None
    name: str | None = None
    docker_tag: str | None = None
    frequency: str | None = None
    timezone: str | None = None
    timezone_id: int | None = None
    enabled: bool | None = None
    release_type: str | None = None
    num_associated_publisher: int | None = None
    external_id: int | None = Field(None, validation_alias=AliasChoices("external_id", "id"))
    next_update_time: int | None = None
    upgrading_stage: int | None = None
    will_start: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


class LocalBrokerPatch(NpaRequest):
    """Local-broker changes, using the gateway's location field names."""

    city: str | None = Field(None, alias="city_name")
    region: str | None = Field(None, alias="region_name")
    country: str | None = Field(None, alias="country_name")
    country_code: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    custom_public_ip: str | None = None
    custom_private_ip: str | None = None
    label_ids: list[str] | None = None
    access_via_public_ip: Literal["NONE", "OFF_PREM", "ON_PREM", "ON_OFF_PREM"] | None = None

    @field_validator("custom_public_ip", "custom_private_ip")
    @classmethod
    def _ipv4(cls, value: str | None) -> str | None:
        if value is not None:
            IPv4Address(value)
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one local-broker field.")
        return self


class LocalBrokerCreate(LocalBrokerPatch):
    name: str


# The 69 IANA zone names ``publisher_upgrade_profile_post_request.timezone``
# accepts (npa_upgrade_profiles.yaml:428-497); the PUT request declares the
# same set (:573-650).  A value outside it is rejected by the gateway.
PUBLISHER_UPGRADE_TIMEZONES: Final[tuple[str, ...]] = (
    "Africa/Cairo",
    "Africa/Casablanca",
    "Africa/Johannesburg",
    "Africa/Nairobi",
    "America/Argentina/Buenos_Aires",
    "America/Caracas",
    "America/Godthab",
    "America/Lima",
    "America/Mazatlan",
    "America/Santiago",
    "America/Tijuana",
    "Asia/Almaty",
    "Asia/Baghdad",
    "Asia/Baku",
    "Asia/Calcutta",
    "Asia/Dhaka",
    "Asia/Harbin",
    "Asia/Jakarta",
    "Asia/Jerusalem",
    "Asia/Kabul",
    "Asia/Karachi",
    "Asia/Kathmandu",
    "Asia/Krasnoyarsk",
    "Asia/Kuala_Lumpur",
    "Asia/Muscat",
    "Asia/Rangoon",
    "Asia/Taipei",
    "Asia/Tehran",
    "Asia/Vladivostok",
    "Asia/Yakutsk",
    "Asia/Yerevan",
    "Atlantic/Azores",
    "Atlantic/Cape_Verde",
    "Australia/Adelaide",
    "Australia/Brisbane",
    "Australia/Darwin",
    "Australia/Hobart",
    "Australia/Perth",
    "Australia/Sydney",
    "Brazil/East",
    "Canada/Atlantic",
    "Canada/Central",
    "Canada/Newfoundland",
    "Canada/Saskatchewan",
    "Europe/Amsterdam",
    "Europe/Athens",
    "Europe/Copenhagen",
    "Europe/Helsinki",
    "Europe/London",
    "Europe/Minsk",
    "Europe/Moscow",
    "Europe/Paris",
    "Europe/Prague",
    "Europe/Sarajevo",
    "Japan",
    "Mexico/General",
    "Pacific/Auckland",
    "Pacific/Fiji",
    "Pacific/Guadalcanal",
    "Pacific/Guam",
    "Pacific/Samoa",
    "Pacific/Tongatapu",
    "US/Alaska",
    "US/Arizona",
    "US/East-Indiana",
    "US/Eastern",
    "US/Hawaii",
    "US/Mountain",
    "US/Pacific",
)


class UpgradeProfileCreate(NpaRequest):
    name: str
    docker_tag: str
    frequency: str
    timezone: str
    release_type: Literal["Beta", "Latest", "Latest-1", "Latest-2"]
    enabled: bool
    timezone_id: int | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        if value not in PUBLISHER_UPGRADE_TIMEZONES:
            raise ValueError(
                f"timezone must be one of the {len(PUBLISHER_UPGRADE_TIMEZONES)} zones the "
                "gateway accepts; see netskope.models.infrastructure."
                "PUBLISHER_UPGRADE_TIMEZONES."
            )
        return value


class UpgradeProfileUpdate(UpgradeProfileCreate):
    """A complete replacement profile, without an implicit pre-write read."""

    id: int


class UpgradeProfileAssignment(NetskopeModel):
    status: str | None = None
    message: str | None = None
    updated: bool | None = None
