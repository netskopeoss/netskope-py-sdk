"""NPA (Netskope Private Access) namespace container.

Groups the NPA sub-APIs under ``client.npa`` and hosts small NPA-wide
utilities (name validation and resource search).

Example::

    result = client.npa.validate_name("private_app", "SSH Server")
    hits = client.npa.search("publishers", "prod")

    for rule in client.npa.policy.rules.list():
        print(rule.rule_name)
"""

from __future__ import annotations

import functools
from typing import Any

from netskope.exceptions import ValidationError
from netskope.models.npa_policy import NpaResourceType, NpaSearchType
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import quote_id
from netskope.resources.local_brokers import AsyncLocalBrokersResource, LocalBrokersResource
from netskope.resources.npa_policy import AsyncNpaPolicyResource, NpaPolicyResource
from netskope.resources.upgrade_profiles import (
    AsyncUpgradeProfilesResource,
    UpgradeProfilesResource,
)

_NAME_VALIDATION_PATH = "/api/v2/infrastructure/npa/namevalidation"
_SEARCH_BASE_PATH = "/api/v2/infrastructure/npa/search"

_VALID_NAME_RESOURCE_TYPES = frozenset(t.value for t in NpaResourceType)
_VALID_SEARCH_TYPES = frozenset(t.value for t in NpaSearchType)


def _build_name_validation_params(resource_type: str, name: str) -> dict[str, Any]:
    if resource_type not in _VALID_NAME_RESOURCE_TYPES:
        raise ValidationError(
            f"Invalid resource_type {resource_type!r}. "
            f"Must be one of: {', '.join(sorted(_VALID_NAME_RESOURCE_TYPES))}"
        )
    return {"resourceType": resource_type, "name": name}


def _search_path(resource_type: str) -> str:
    if resource_type not in _VALID_SEARCH_TYPES:
        raise ValidationError(
            f"Invalid resource_type {resource_type!r}. "
            f"Must be one of: {', '.join(sorted(_VALID_SEARCH_TYPES))}"
        )
    return f"{_SEARCH_BASE_PATH}/{quote_id(resource_type)}"


class NpaResource(SyncResource):
    """Top-level NPA namespace: ``client.npa.policy`` plus NPA-wide utilities.

    Additional sub-namespaces (e.g. ``upgrade_profiles``, ``local_brokers``)
    are added here as they land in the SDK.
    """

    @functools.cached_property
    def policy(self) -> NpaPolicyResource:
        """Access the NPA policy rules and groups API."""
        return NpaPolicyResource(self._transport)

    @functools.cached_property
    def upgrade_profiles(self) -> UpgradeProfilesResource:
        """Access the publisher upgrade profiles API."""
        return UpgradeProfilesResource(self._transport)

    @functools.cached_property
    def local_brokers(self) -> LocalBrokersResource:
        """Access the local brokers API."""
        return LocalBrokersResource(self._transport)

    def validate_name(self, resource_type: str, name: str) -> dict[str, Any]:
        """Validate a resource name for uniqueness and correctness.

        Args:
            resource_type: One of ``publisher``, ``publisher_upgrade_profile``,
                ``tag``, ``policy``, ``private_app``, ``local_broker``
                (see :class:`~netskope.models.npa_policy.NpaResourceType`).
            name: The candidate name to validate.

        Raises:
            netskope.exceptions.ValidationError: If *resource_type* is not
                a supported value.
        """
        params = _build_name_validation_params(resource_type, name)
        return self._get(_NAME_VALIDATION_PATH, **params)

    def search(self, resource_type: str, query: str) -> dict[str, Any]:
        """Search NPA resources by query string.

        Args:
            resource_type: ``publishers`` or ``private_apps``
                (see :class:`~netskope.models.npa_policy.NpaSearchType`).
            query: A filter expression, e.g. ``'name sw myapp'`` or
                ``'name has prod and in_policy eq yes'``. Supported operators:
                ``eq``, ``ne``, ``sw``, ``has``, ``in``, ``pr`` (a bare string
                without an operator is rejected by the API with HTTP 400).

        Raises:
            netskope.exceptions.ValidationError: If *resource_type* is not
                a supported value.
        """
        return self._get(_search_path(resource_type), query=query)


class AsyncNpaResource(AsyncResource):
    """Async top-level NPA namespace."""

    @functools.cached_property
    def policy(self) -> AsyncNpaPolicyResource:
        """Access the NPA policy rules and groups API."""
        return AsyncNpaPolicyResource(self._transport)

    @functools.cached_property
    def upgrade_profiles(self) -> AsyncUpgradeProfilesResource:
        """Access the publisher upgrade profiles API."""
        return AsyncUpgradeProfilesResource(self._transport)

    @functools.cached_property
    def local_brokers(self) -> AsyncLocalBrokersResource:
        """Access the local brokers API."""
        return AsyncLocalBrokersResource(self._transport)

    async def validate_name(self, resource_type: str, name: str) -> dict[str, Any]:
        """Validate a resource name.  See :meth:`NpaResource.validate_name`."""
        params = _build_name_validation_params(resource_type, name)
        return await self._get(_NAME_VALIDATION_PATH, **params)

    async def search(self, resource_type: str, query: str) -> dict[str, Any]:
        """Search NPA resources.  See :meth:`NpaResource.search`."""
        return await self._get(_search_path(resource_type), query=query)
