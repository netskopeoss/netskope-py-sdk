"""Typed CCI applications, tag records, and explicit mutation inputs."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from netskope.models.common import NetskopeModel


class _CciRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def no_explicit_nulls(self) -> Self:
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Omit unused fields instead of supplying null.")
        return self


class CciAppQuery(_CciRequest):
    """Select applications with exactly one gateway-supported selector."""

    apps: list[str] | None = Field(None, min_length=1, max_length=100)
    category: str | None = None
    ccl: Literal["poor", "low", "medium", "high", "excellent"] | None = None
    connector: Literal["1", "true"] | None = None
    discovered: Literal[True] | None = None
    domain: str | None = None
    ids: list[str] | None = Field(None, min_length=1, max_length=100)
    tag: str | None = None
    updated: Literal["all"] | None = None
    limit: int | None = Field(None, ge=0)
    offset: int | None = Field(None, ge=0)

    @field_validator("apps", "ids")
    @classmethod
    def query_list_values(cls, values: list[str] | None) -> list[str] | None:
        if values is not None and any(not value.strip() or ";" in value for value in values):
            raise ValueError("Query names and IDs must be nonempty and cannot contain semicolons.")
        return values

    @field_validator("discovered", mode="before")
    @classmethod
    def discovery_flag(cls, value: object) -> object:
        if value is not None and value is not True:
            raise ValueError("discovered accepts only True.")
        return value

    @model_validator(mode="after")
    def one_selector(self) -> Self:
        selected = self.model_fields_set - {"limit", "offset"}
        if len(selected) != 1:
            raise ValueError("Choose exactly one CCI selector; limit and offset may accompany it.")
        return self


class CciApplication(NetskopeModel):
    app_name: str | None = None
    id: int | None = None
    cci: int | None = None
    ccl: str | None = None
    category_name: str | None = None
    organisation: str | None = None


class CciTagName(RootModel[str]):
    """A tag name from the tenant-wide catalog."""


class CciAppTags(NetskopeModel):
    app_type: str | None = None
    id: int | None = None
    sanctioned: str | None = None
    tags: list[str] = Field(default_factory=list)


class CciAppTagMap(RootModel[dict[str, CciAppTags]]):
    """Application names mapped to their tag memberships."""


class CciTagRule(NetskopeModel):
    attribute: str | None = None
    condition: str | None = None
    value: list[str] | None = None


class CciTagDetails(NetskopeModel):
    tag_name: str | None = None
    description: str | None = None
    applications_count: int | None = None
    policies: int | None = None
    rules_applicable: str | None = None
    rules: list[CciTagRule] = Field(default_factory=list)


class CciTagRuleInput(_CciRequest):
    attribute: str
    condition: str
    value: list[str]


class CciTagCreate(_CciRequest):
    # ``ids`` carries application IDs, which ``appTagExample``; the example the
    # ``POST /cci/tags`` body points at (services/cci.yaml:48-57); writes as
    # integers, so both JSON types are accepted and forwarded unchanged.
    name: str = Field(alias="tag", min_length=1, max_length=75)
    apps: list[str] | None = Field(None, min_length=1, max_length=100)
    ids: list[str | int] | None = Field(None, min_length=1, max_length=100)
    rules: list[CciTagRuleInput] | None = Field(None, min_length=1)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def tag_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_\[\]() -]+", value) or "  " in value or not value.strip():
            raise ValueError("Tag names must use the gateway-supported characters and spacing.")
        return value

    @model_validator(mode="after")
    def require_membership(self) -> Self:
        if self.apps is not None and self.ids is not None:
            raise ValueError("apps and ids are mutually exclusive.")
        if not (self.apps or self.ids or self.rules):
            raise ValueError("Provide apps, ids, or rules when creating a tag.")
        if self.description is not None and not self.rules:
            raise ValueError("description is supported only with rules.")
        return self


class CciTagPatch(_CciRequest):
    """Explicit append/remove membership changes; no implicit replacement."""

    action: Literal["append", "remove"]
    apps: list[str] | None = Field(None, min_length=1, max_length=100)
    # Application IDs, integers in the contract's own example (services/cci.yaml:48-57).
    ids: list[str | int] | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def one_membership(self) -> Self:
        if (self.apps is None) == (self.ids is None):
            raise ValueError("Provide exactly one of apps or ids.")
        return self


class CciTagMutationReceipt(NetskopeModel):
    status: str | None = None
    status_code: int | None = None
    message: str | None = None
    tag: str | None = None
    action: str | None = None
    apps: list[str] | None = None
