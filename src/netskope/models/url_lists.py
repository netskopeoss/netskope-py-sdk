"""Models for the Netskope URL List (Policy) API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from netskope.models.common import NetskopeModel


class UrlListType(StrEnum):
    """URL list matching strategy."""

    EXACT = "exact"
    REGEX = "regex"


class UrlList(NetskopeModel):
    """A Netskope URL allow/block list.

    ``Urllist`` (``policy/urllist.yaml:87-121``) declares ``pending`` as an
    integer — ``1`` for a list with undeployed changes — so it is read as one
    rather than coerced through a boolean that would reject any other value.

    Example::

        for url_list in client.url_lists.list():
            print(f"{url_list.name}: {len(url_list.urls)} entries")
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    urls: list[str] = Field(default_factory=list)
    pending: int | bool | None = None
    modify_by: str | None = None
    modify_time: int | str | None = None
    modify_type: str | None = None


class PolicyDeployment(NetskopeModel):
    """Acknowledgment of a URL-list deployment request.

    ``POST /urllist/deploy`` answers with the array of URL lists it applied
    (``policy/urllist.yaml:209-217``), which carries no status field; those
    records land in ``urllists``.  A tenant that answers with a status object
    instead fills ``status``/``message``.
    """

    status: str | int | None = None
    message: str | None = None
    id: int | str | None = None
    urllists: list[UrlList] = Field(default_factory=list)
