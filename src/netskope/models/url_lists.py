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

    Example::

        for url_list in client.url_lists.list():
            print(f"{url_list.name}: {len(url_list.urls)} entries")
    """

    id: int | None = None
    name: str | None = None
    type: str | None = None
    urls: list[str] = Field(default_factory=list)
    count: int | None = None
    pending: bool | None = None
    modify_by: str | None = None
    modify_time: int | str | None = None
    modify_type: str | None = None
    json_version: int | None = None
