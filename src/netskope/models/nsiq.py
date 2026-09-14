"""Typed NSIQ lookup, recategorization, and URL false-positive contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel


class UrlLookup(AdminRequest):
    urls: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1, max_length=100)
    disable_dns_lookup: bool = False
    category: Literal["casb", "swg"] | None = None


class UrlCategory(NetskopeModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None


class UrlListMatch(NetskopeModel):
    id: str | None = None
    name: str | None = None


class UrlLookupReport(NetskopeModel):
    """``url-lookup-report`` (nsiq/url_lookup.yaml).

    The schema declares no required properties, so a sparse row must not
    reject the page it sits in.
    """

    url: str | None = None
    categories: list[UrlCategory] = Field(default_factory=list)
    url_lists: list[UrlListMatch] = Field(default_factory=list)
    dynamic_classification: bool | None = None
    site: str | None = None
    app: str | None = None
    resolved_ip: str | None = None


class UrlRecategorization(AdminRequest):
    url: str = Field(min_length=1, max_length=2000)
    suggested_categories: list[Annotated[str, Field(min_length=1)]] = Field(min_length=1)


class RecategorizationRequest(AdminRequest):
    """Email is optional in the pinned gateway schema; no current-category field exists."""

    recat_requests: list[UrlRecategorization] = Field(min_length=1)
    email: str | None = None
    justification: str | None = Field(None, max_length=2000)


class RecategorizationUrl(NetskopeModel):
    """``RecatUrlId`` (nsiq/url_recategorization.yaml:93-107); nothing is required."""

    id: str | None = None
    url: str | None = None
    status: str | None = None


class RecategorizationReceipt(NetskopeModel):
    """``SubmissionDetail`` (nsiq/url_recategorization.yaml:150-158); nothing is required."""

    task_id: str | None = None
    urls: list[RecategorizationUrl] = Field(default_factory=list)


class UrlFalsePositive(AdminRequest):
    incident_id: str = Field(min_length=1)
    url: str | None = None
    page: str | None = None
    description: str | None = None
    threat_match_value: str | None = None
    current_category_id: list[int] | None = None
    affected_version: str | None = None
    timestamp: int | None = None


class UrlFalsePositiveRequest(AdminRequest):
    user_email: str = Field(min_length=1)
    fp_data: list[UrlFalsePositive] = Field(min_length=1)
    tenant_user_name: str | None = None


class FalsePositiveTicket(NetskopeModel):
    """``FPTicketInfo`` (nsiq/fp_submission.yaml:45-55) — nothing is required."""

    system: str | None = None
    ticket_id: str | None = None


class FalsePositiveReceipt(NetskopeModel):
    """``FPCaseInfo`` (nsiq/fp_submission.yaml:30-36) — nothing is required."""

    incident_id: str | None = None
    tickets: list[FalsePositiveTicket] = Field(default_factory=list)
