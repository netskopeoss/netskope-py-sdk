"""Models for the Netskope Private Apps (NPA) API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import AliasChoices, Field, JsonValue, field_validator, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class PrivateAppProtocol(StrEnum):
    """Supported private-app protocols."""

    TCP = "TCP"
    UDP = "UDP"
    TCP_UDP = "TCP/UDP"


class PrivateAppTag(NetskopeModel):
    """A tag attached to one or more private applications.

    Example::

        for tag in client.private_apps.tags.list():
            print(f"{tag.tag_id}: {tag.tag_name}")
    """

    tag_id: int | None = None
    tag_name: str | None = None


def _protocol_ports(protocols: Any) -> list[str]:
    """Collect the ports the response carries inside its protocol entries.

    ``private_apps_item.protocols`` (``npa_apps_private.yaml:180-183``) holds
    ``protocol_response_item`` objects whose port is a scalar ``port``
    (``:402-422``), while the same-named schema in ``npa_generic.yaml:38-46``
    and ``npa_private_publisher.yaml:16-24`` holds a ``ports`` array.  Both
    shapes are read, in the order the API listed them, without duplicates.
    """
    ports: list[str] = []
    if not isinstance(protocols, list):
        return ports
    for entry in protocols:
        if not isinstance(entry, dict):
            continue
        listed = entry.get("ports")
        candidates: list[Any] = listed if isinstance(listed, list) else [entry.get("port")]
        for candidate in candidates:
            if isinstance(candidate, (str, int)) and not isinstance(candidate, bool):
                text = str(candidate)
                if text and text not in ports:
                    ports.append(text)
    return ports


class PrivateApp(NetskopeModel):
    """A Netskope Private Application (ZTNA).

    ``private_apps_item`` (``npa_apps_private.yaml:133-231``) has no top-level
    ``port`` — every port lives inside a ``protocols`` entry — so ``port`` is
    filled in from those entries (comma-joined when the app exposes several)
    rather than left empty.  The publisher assignments the API returns are
    ``service_publisher_assignments`` (``:201-204``); ``publishers`` is the
    SDK's older name for the same value.

    NPA search answers with ``private_apps_response_item``
    (``npa_generic.yaml:70-117``), which names the record ``id`` and ``name``
    rather than ``app_id`` and ``app_name``; both spellings reach the same two
    attributes, and the steering list's own ``app_id``/``app_name`` still win
    where a record carries both.

    Example::

        for app in client.private_apps.list():
            print(f"{app.app_name} → {app.host}:{app.port}")
    """

    app_id: int | None = Field(None, validation_alias=AliasChoices("app_id", "id"))
    app_name: str | None = Field(None, validation_alias=AliasChoices("app_name", "name"))
    host: str | None = None
    port: str | None = None
    private_app_protocol: str | None = None
    protocols: list[Any] | None = None
    publishers: list[dict[str, Any]] | None = Field(
        None, validation_alias=AliasChoices("publishers", "service_publisher_assignments")
    )
    service_publisher_assignments: list[dict[str, Any]] | None = None
    use_publisher_dns: bool | None = None
    clientless_access: bool | None = None
    trust_self_signed_certs: bool | None = None
    tags: list[dict[str, Any]] | None = Field(default_factory=list)
    reachability: Any | None = None

    @model_validator(mode="before")
    @classmethod
    def _port_from_protocols(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("port") is None:
            ports = _protocol_ports(data.get("protocols"))
            if ports:
                return {**data, "port": ",".join(ports)}
        return data


class PrivateAppProtocolSpec(NpaRequest):
    """A transport and its port or port range in a private-app request."""

    type: Literal["tcp", "udp"]
    port: str


class PrivateAppPublisherSpec(NpaRequest):
    publisher_id: str
    publisher_name: str | None = None


class PrivateAppTagSpec(NpaRequest):
    tag_name: str


class PrivateAppPathSpec(NpaRequest):
    path: str
    portal_display_name: str | None = None


class PrivateAppPatch(NpaRequest):
    """Explicit private-app changes. Omitted fields are not serialized."""

    nullable_fields = frozenset({"use_publisher_dns", "trust_self_signed_certs"})

    app_name: str | None = None
    host: str | None = None
    protocols: list[PrivateAppProtocolSpec] | None = None
    publishers: list[PrivateAppPublisherSpec] | None = None
    tags: list[PrivateAppTagSpec] | None = None
    publisher_tags: list[PrivateAppTagSpec] | None = None
    clientless_access: bool | None = None
    use_publisher_dns: bool | None = None
    trust_self_signed_certs: bool | None = None
    allow_unauthenticated_cors: bool | None = None
    allow_uri_bypass: bool | None = None
    uribypass_header_value: str | None = None
    bypass_uris: list[str] | None = None
    app_option: dict[str, JsonValue] | None = None
    upgrade_insecure_request: bool | None = None
    is_user_portal_app: bool | None = None
    labels: list[dict[str, JsonValue]] | None = None
    hide_app_in_portal: bool | None = None
    custom_host: str | None = None
    paths: list[PrivateAppPathSpec] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one private-app field is required.")
        return self


class PrivateAppCreate(PrivateAppPatch):
    app_name: str
    host: str


class PrivateAppMutationResult(NetskopeModel):
    """Acknowledgment of a private-app bulk mutation."""

    status: str | int | None = None
    message: str | None = None


class PrivateAppPolicyReference(NetskopeModel):
    """Policy references for one private app or tag."""

    app_id: int | str | None = None
    tag_id: int | str | None = None
    num_in_use: int | str | None = None
    policy_in_use: str | None = None
    policies: list[str] = Field(default_factory=list)


class PrivateAppPolicyUsage(NetskopeModel):
    """Policy references returned for a selected set of private apps or tags.

    An acknowledgment that carries no ``data`` reports no policy references,
    which is a legitimate answer for apps that are in no policy at all.
    """

    status: str | int | None = None
    data: list[PrivateAppPolicyReference] | dict[str, list[str]] = Field(default_factory=list)

    @field_validator("data", mode="before")
    @classmethod
    def _absent_data(cls, v: Any) -> Any:
        return [] if v is None else v


class PrivateAppDiscoveryPublisher(NpaRequest):
    publisher_id: str
    publisher_cn: str | None = None
    publisher_name: str | None = None


class PrivateAppDiscoverySelection(NpaRequest):
    host: list[str] | None = None
    organization_units: list[str] | None = None
    publishers: list[PrivateAppDiscoveryPublisher] | None = None
    status: Literal["ENABLED", "DISABLED"] | None = None
    users: list[str] | None = None
    user_groups: list[str] | None = Field(None, alias="userGroups")


class PrivateAppDiscoveryRequest(PrivateAppDiscoverySelection):
    """Supports the gateway's documented flat schema and wrapped request example."""

    settings: PrivateAppDiscoverySelection | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Discovery settings cannot be empty.")
        if "settings" in self.model_fields_set and len(self.model_fields_set) > 1:
            raise ValueError("Use either wrapped settings or flat settings, not both.")
        return self


class PrivateAppDiscoveryPublisherInfo(NetskopeModel):
    publisher_id: str | int | None = None
    publisher_cn: str | None = None
    publisher_name: str | None = None


class PrivateAppDiscoveryConfiguration(NetskopeModel):
    """Discovery values returned by the API, including future settings."""

    host: list[str] | None = None
    organization_units: list[str] | None = None
    publishers: list[PrivateAppDiscoveryPublisherInfo] | None = None
    status: str | None = None
    users: list[str] | None = None
    user_groups: list[str] | None = Field(None, alias="userGroups")


class PrivateAppDiscoverySettings(NetskopeModel):
    id: int | None = None
    settings: PrivateAppDiscoveryConfiguration | None = None
    created_at: str | None = None
    updated_at: str | None = None
