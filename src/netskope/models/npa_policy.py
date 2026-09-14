"""Models for the Netskope NPA (Private Access) Policy API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import AliasChoices, Field, field_serializer, model_validator

from netskope.models._npa_requests import NpaRequest
from netskope.models.common import NetskopeModel


class NpaResourceType(StrEnum):
    """Resource types accepted by NPA name validation (gateway spec enum)."""

    PUBLISHER = "publisher"
    PUBLISHER_UPGRADE_PROFILE = "publisher_upgrade_profile"
    TAG = "tag"
    POLICY = "policy"
    PRIVATE_APP = "private_app"
    LOCAL_BROKER = "local_broker"


class NpaSearchType(StrEnum):
    """Resource types accepted by NPA search."""

    PUBLISHERS = "publishers"
    PRIVATE_APPS = "private_apps"


class NpaTagType(StrEnum):
    """Tag scope for NPA name validation.

    ``GET /npa/namevalidation`` takes ``tag_type`` as the string ``"1"`` or
    ``"2"``, "required only for resourceType tag"
    (``npa_generic.yaml:282-292``).
    """

    PRIVATE_APP = "1"
    PUBLISHER = "2"


class NpaRuleAction(NpaRequest):
    action_name: Literal["allow", "block"]


class NpaPeriodicReauth(NpaRequest):
    reauth_interval: str | None = None
    reauth_interval_unit: str | None = None


class NpaUserConfidence(NpaRequest):
    operator: Literal["lt", "gt"]
    index: Literal["350", "351", "650", "651"]

    @model_validator(mode="after")
    def valid_threshold(self) -> Self:
        allowed = ("351", "651") if self.operator == "lt" else ("350", "650")
        if self.index not in allowed:
            raise ValueError("The confidence index is not valid for this operator.")
        return self


class NpaRuleData(NpaRequest):
    """Known NPA rule conditions and action, validated before a mutation."""

    access_method: list[Literal["Client", "Clientless", "Enterprise Browser"]] | None = None
    negate_net_location: bool | None = Field(None, alias="b_negateNetLocation")
    negate_src_countries: bool | None = Field(None, alias="b_negateSrcCountries")
    classification: str | None = None
    periodic_reauth: NpaPeriodicReauth | None = None
    json_version: int | None = None
    device_classification_id: list[int] | None = None
    match_criteria_action: NpaRuleAction | None = None
    net_location_obj: list[str] | None = None
    user_confidence: NpaUserConfidence | None = None
    organization_units: list[str] | None = None
    policy_type: Literal["private-app"] | None = None
    private_app_tag_ids: list[str] | None = Field(None, alias="privateAppTagIds")
    private_app_tags: list[str] | None = Field(None, alias="privateAppTags")
    private_apps: list[str] | None = Field(None, alias="privateApps")
    src_countries: list[str] | None = Field(None, alias="srcCountries")
    user_groups: list[str] | None = Field(None, alias="userGroups")
    user_type: Literal["user"] | None = Field(None, alias="userType")
    users: list[str] | None = None
    version: int | None = None


class NpaRuleOrder(NpaRequest):
    order: Literal["top", "bottom", "before", "after"] | None = None
    position: int | None = None
    rule_id: int | None = None
    rule_name: str | None = None


class NpaPolicyRulePatch(NpaRequest):
    description: str | None = None
    enabled: bool | Literal["0", "1"] | None = None
    group_id: str | int | None = None
    group_name: str | None = None
    rule_data: NpaRuleData | None = None
    rule_name: str | None = None
    rule_order: NpaRuleOrder | None = None

    @field_serializer("enabled")
    def serialize_enabled(self, value: bool | str | None) -> str | None:
        return ("1" if value else "0") if isinstance(value, bool) else value

    @field_serializer("group_id")
    def serialize_group_id(self, value: str | int | None) -> str | None:
        return str(value) if value is not None else None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one policy rule field is required.")
        return self


class NpaPolicyRuleCreate(NpaPolicyRulePatch):
    rule_name: str
    rule_data: NpaRuleData

    @model_validator(mode="after")
    def require_application_selection(self) -> Self:
        data = self.rule_data
        if not (data.private_apps or data.private_app_tags or data.private_app_tag_ids):
            raise ValueError(
                "rule_data must select privateApps, privateAppTags, or privateAppTagIds."
            )
        return self


class NpaGroupOrder(NpaRequest):
    """Where a new policy group lands relative to an existing one.

    Serialized as the legacy single ``group_order`` object.
    ``npa_policygroup_request`` (``policy/npa_policygroup.yaml:7-20``) nests a
    second ``group_order`` inside the first, whose wrapper carries no other
    property. The wrapper permits additional properties, so the legacy body
    remains schema-valid, but their interpretation needs upstream clarification.
    """

    group_id: str
    order: Literal["before", "after"]


class NpaPolicyGroupPatch(NpaRequest):
    group_name: str | None = None
    group_order: NpaGroupOrder | None = None
    modify_by: str | None = None
    modify_type: str | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one policy group field is required.")
        return self


class NpaPolicyGroupCreate(NpaPolicyGroupPatch):
    group_name: str
    group_order: NpaGroupOrder


class NpaNameValidation(NetskopeModel):
    """The result of validating an NPA resource name.

    ``validate_name_response`` (``npa_generic.yaml:188-199``) marks nothing
    required and declares no ``message``, so a response that reports neither
    parses with both left unset rather than raising.
    """

    is_valid_name: bool | None = Field(
        None, validation_alias=AliasChoices("is_valid_name", "valid")
    )
    message: str | None = None


class NpaPolicyRule(NetskopeModel):
    """An NPA policy rule.

    Note:
        The API represents ``enabled`` as the string ``"1"`` or ``"0"``,
        not a boolean — it is preserved as returned.
        ``npa_policy_response_item`` (``policy/npa_policy.yaml:54-64``)
        declares only ``rule_data``, ``rule_id`` and ``rule_name``; the
        remaining fields are modelled because live responses carry them, and
        any further key stays reachable through the model's extras.
    """

    rule_id: int | None = None
    rule_name: str | None = None
    enabled: str | None = None
    group_id: int | str | None = None
    group_name: str | None = None
    action: str | None = None
    rule_data: dict[str, Any] | None = None


class NpaPolicyGroup(NetskopeModel):
    """An NPA policy group — a named container for policy rules.

    Note:
        The API returns ``group_id`` as a string in create responses (e.g.
        ``"18"``) but may return an integer elsewhere; both are preserved.
        ``can_be_edited_deleted`` is a string like ``"True"`` in live
        responses even though the spec declares it an integer.
    """

    group_id: int | str | None = None
    group_name: str | None = None
    can_be_edited_deleted: str | int | bool | None = None
