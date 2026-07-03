"""Models for the Netskope NPA (Private Access) Policy API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

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


class NpaPolicyRule(NetskopeModel):
    """An NPA policy rule.

    Note:
        The API represents ``enabled`` as the string ``"1"`` or ``"0"``,
        not a boolean — it is preserved as returned.
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
