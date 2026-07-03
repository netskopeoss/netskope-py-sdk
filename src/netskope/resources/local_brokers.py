"""Local brokers resource — manage NPA local brokers and broker config.

Example::

    for broker in client.npa.local_brokers.list():
        print(f"{broker.name} — registered={broker.registered}")

    broker = client.npa.local_brokers.create("dc1-broker", city="Cupertino")
    token = client.npa.local_brokers.create_registration_token(broker.id)
"""

from __future__ import annotations

import builtins
from typing import Any

from netskope.exceptions import NetskopeError, ValidationError
from netskope.models.infrastructure import BrokerPublicIpAccess, LocalBroker, LocalBrokerConfig
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import extract_item, extract_list

_PATH = "/api/v2/infrastructure/lbrokers"

# Literal sub-path — must never be built via the /{id} route.
_CONFIG_PATH = f"{_PATH}/brokerconfig"

_VALID_PUBLIC_IP_ACCESS = frozenset(member.value for member in BrokerPublicIpAccess)


def _validate_public_ip_access(value: str) -> str:
    if value not in _VALID_PUBLIC_IP_ACCESS:
        raise ValidationError(
            f"Invalid access_via_public_ip {value!r}. "
            f"Must be one of: {', '.join(sorted(_VALID_PUBLIC_IP_ACCESS))}"
        )
    return str(value)


def _build_broker_payload(
    city: str | None,
    region: str | None,
    country: str | None,
    country_code: str | None,
    latitude: float | None,
    longitude: float | None,
    custom_public_ip: str | None,
    custom_private_ip: str | None,
    access_via_public_ip: str | None,
) -> dict[str, Any]:
    """Build the shared create/update body using the gateway spec key names.

    The API expects ``city_name`` / ``region_name`` / ``country_name`` (not
    the bare ``city`` / ``region`` / ``country`` used by the SDK parameters).
    """
    payload: dict[str, Any] = {}
    if city is not None:
        payload["city_name"] = city
    if region is not None:
        payload["region_name"] = region
    if country is not None:
        payload["country_name"] = country
    if country_code is not None:
        payload["country_code"] = country_code
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude
    if custom_public_ip is not None:
        payload["custom_public_ip"] = custom_public_ip
    if custom_private_ip is not None:
        payload["custom_private_ip"] = custom_private_ip
    if access_via_public_ip is not None:
        payload["access_via_public_ip"] = _validate_public_ip_access(access_via_public_ip)
    return payload


def _extract_token(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, dict) and data.get("token") is not None:
        return str(data["token"])
    if body.get("token") is not None:
        return str(body["token"])
    raise NetskopeError(f"Registration token missing from response: {body!r}")


class LocalBrokersResource(SyncResource):
    """Synchronous interface to ``/api/v2/infrastructure/lbrokers``."""

    def list(self) -> builtins.list[LocalBroker]:
        """List all local brokers.

        Returns:
            A list of :class:`~netskope.models.infrastructure.LocalBroker`.
        """
        body = self._get(_PATH)
        return [LocalBroker.model_validate(item) for item in extract_list(body)]

    def get(self, broker_id: int) -> LocalBroker:
        """Get a local broker by ID.

        Args:
            broker_id: The numeric local broker identifier.
        """
        body = self._get(f"{_PATH}/{broker_id}")
        return LocalBroker.model_validate(extract_item(body))

    def create(
        self,
        name: str,
        *,
        city: str | None = None,
        region: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        custom_public_ip: str | None = None,
        custom_private_ip: str | None = None,
        access_via_public_ip: str | None = None,
    ) -> LocalBroker:
        """Create a local broker.

        Args:
            name: Unique display name for the broker.
            city: City of the deployment (sent as ``city_name``).
            region: Region/state (sent as ``region_name``).
            country: Country (sent as ``country_name``).
            country_code: ISO country code, e.g. ``"US"``.
            latitude: Latitude in decimal degrees (-90 to 90).
            longitude: Longitude in decimal degrees (-180 to 180).
            custom_public_ip: Custom public IPv4 address of the broker.
            custom_private_ip: Custom private IPv4 address of the broker.
            access_via_public_ip: Public-IP access policy — one of
                :class:`~netskope.models.infrastructure.BrokerPublicIpAccess`
                (``NONE``, ``OFF_PREM``, ``ON_PREM``, ``ON_OFF_PREM``).

        Raises:
            netskope.exceptions.ValidationError: If *access_via_public_ip*
                is not a supported value.
        """
        payload = {
            "name": name,
            **_build_broker_payload(
                city,
                region,
                country,
                country_code,
                latitude,
                longitude,
                custom_public_ip,
                custom_private_ip,
                access_via_public_ip,
            ),
        }
        body = self._post(_PATH, json=payload)
        return LocalBroker.model_validate(extract_item(body))

    def update(
        self,
        broker_id: int,
        *,
        city: str | None = None,
        region: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        custom_public_ip: str | None = None,
        custom_private_ip: str | None = None,
        access_via_public_ip: str | None = None,
    ) -> LocalBroker:
        """Update a local broker.

        Only the provided fields are sent.  Note the API's update schema
        does not accept a new ``name`` — brokers cannot be renamed here.

        Args:
            broker_id: The numeric local broker identifier.
            city: City of the deployment (sent as ``city_name``).
            region: Region/state (sent as ``region_name``).
            country: Country (sent as ``country_name``).
            country_code: ISO country code.
            latitude: Latitude in decimal degrees.
            longitude: Longitude in decimal degrees.
            custom_public_ip: Custom public IPv4 address.
            custom_private_ip: Custom private IPv4 address.
            access_via_public_ip: Public-IP access policy (see
                :class:`~netskope.models.infrastructure.BrokerPublicIpAccess`).

        Raises:
            netskope.exceptions.ValidationError: If *access_via_public_ip*
                is not a supported value.
        """
        payload = _build_broker_payload(
            city,
            region,
            country,
            country_code,
            latitude,
            longitude,
            custom_public_ip,
            custom_private_ip,
            access_via_public_ip,
        )
        body = self._put(f"{_PATH}/{broker_id}", json=payload)
        return LocalBroker.model_validate(extract_item(body))

    def delete(self, broker_id: int) -> None:
        """Delete a local broker.

        Args:
            broker_id: The numeric local broker identifier.
        """
        self._delete(f"{_PATH}/{broker_id}")

    def get_config(self) -> LocalBrokerConfig:
        """Get the tenant-wide local broker hostname configuration."""
        body = self._get(_CONFIG_PATH)
        return LocalBrokerConfig.model_validate(extract_item(body))

    def update_config(self, hostname: str) -> LocalBrokerConfig:
        """Update the tenant-wide local broker hostname configuration.

        Args:
            hostname: Hostname to set in the broker configuration.
        """
        body = self._put(_CONFIG_PATH, json={"hostname": hostname})
        return LocalBrokerConfig.model_validate(extract_item(body))

    def create_registration_token(self, broker_id: int) -> str:
        """Generate a registration token for a local broker.

        Args:
            broker_id: The numeric local broker identifier.

        Returns:
            The registration token string.

        Raises:
            netskope.exceptions.NetskopeError: If no token is present in
                the response.
        """
        body = self._post(f"{_PATH}/{broker_id}/registrationtoken")
        return _extract_token(body)


class AsyncLocalBrokersResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/infrastructure/lbrokers``."""

    async def list(self) -> builtins.list[LocalBroker]:
        """List all local brokers."""
        body = await self._get(_PATH)
        return [LocalBroker.model_validate(item) for item in extract_list(body)]

    async def get(self, broker_id: int) -> LocalBroker:
        """Get a local broker by ID."""
        body = await self._get(f"{_PATH}/{broker_id}")
        return LocalBroker.model_validate(extract_item(body))

    async def create(
        self,
        name: str,
        *,
        city: str | None = None,
        region: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        custom_public_ip: str | None = None,
        custom_private_ip: str | None = None,
        access_via_public_ip: str | None = None,
    ) -> LocalBroker:
        """Create a local broker.

        See :meth:`LocalBrokersResource.create`.
        """
        payload = {
            "name": name,
            **_build_broker_payload(
                city,
                region,
                country,
                country_code,
                latitude,
                longitude,
                custom_public_ip,
                custom_private_ip,
                access_via_public_ip,
            ),
        }
        body = await self._post(_PATH, json=payload)
        return LocalBroker.model_validate(extract_item(body))

    async def update(
        self,
        broker_id: int,
        *,
        city: str | None = None,
        region: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        custom_public_ip: str | None = None,
        custom_private_ip: str | None = None,
        access_via_public_ip: str | None = None,
    ) -> LocalBroker:
        """Update a local broker.

        See :meth:`LocalBrokersResource.update`.
        """
        payload = _build_broker_payload(
            city,
            region,
            country,
            country_code,
            latitude,
            longitude,
            custom_public_ip,
            custom_private_ip,
            access_via_public_ip,
        )
        body = await self._put(f"{_PATH}/{broker_id}", json=payload)
        return LocalBroker.model_validate(extract_item(body))

    async def delete(self, broker_id: int) -> None:
        """Delete a local broker."""
        await self._delete(f"{_PATH}/{broker_id}")

    async def get_config(self) -> LocalBrokerConfig:
        """Get the tenant-wide local broker hostname configuration."""
        body = await self._get(_CONFIG_PATH)
        return LocalBrokerConfig.model_validate(extract_item(body))

    async def update_config(self, hostname: str) -> LocalBrokerConfig:
        """Update the tenant-wide local broker hostname configuration."""
        body = await self._put(_CONFIG_PATH, json={"hostname": hostname})
        return LocalBrokerConfig.model_validate(extract_item(body))

    async def create_registration_token(self, broker_id: int) -> str:
        """Generate a registration token for a local broker.

        See :meth:`LocalBrokersResource.create_registration_token`.
        """
        body = await self._post(f"{_PATH}/{broker_id}/registrationtoken")
        return _extract_token(body)
