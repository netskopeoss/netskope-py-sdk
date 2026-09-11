"""Remote-browser reference data and operation-specific template responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from netskope.models.common import NetskopeModel


class RbiApplication(NetskopeModel):
    name: str = Field(alias="appName")
    accounts: list[str] = Field(default_factory=list)


class RbiApplications(NetskopeModel):
    """``GET /rbi/applications`` 200 body (rbi/templates.yaml:7).

    Only ``message`` and ``status`` are required there, so a reply that omits
    ``applications`` still decodes as an empty mapping.
    """

    applications: dict[str, RbiApplication] = Field(default_factory=dict)
    status: str | None = None
    message: str | None = None


class RbiBrowser(NetskopeModel):
    name: str = Field(alias="browserName")


class RbiCategory(NetskopeModel):
    name: str = Field(alias="appCategory")
    category: list[str]
    activities: list[str] = Field(default_factory=list)


class RbiTemplateMetadata(NetskopeModel):
    id: str = Field(alias="template_id")
    type: str | None = Field(None, alias="template_type")
    status: str | None = Field(None, alias="template_status")
    modification_time: datetime | None = None
    modification_user: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _identity_as_text(cls, value: Any) -> Any:
        """Templates are addressed by id as text, whichever JSON type carries it."""
        return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


class RbiToggle(NetskopeModel):
    enabled: bool


class RbiColoredFrame(RbiToggle):
    color: str


class RbiPopupMessage(RbiToggle):
    border_color: str
    position: str
    logo_image: str
    logo_size: str
    message: str
    ack_button_text: str


class RbiInspection(RbiToggle):
    config_id: str | None = None
    unsupported_file_types_action: str | None = None


class RbiThirdPartyInspection(NetskopeModel):
    upload_inspection: RbiInspection
    download_inspection: RbiInspection


class RbiTemplateSettings(NetskopeModel):
    name: str | None = None
    asterisk_prefix: RbiToggle | None = None
    colored_frame: RbiColoredFrame | None = None
    popup_message: RbiPopupMessage | None = None
    file_download: RbiToggle | None = None
    file_upload: RbiToggle | None = None
    copy_from_isolated_page: RbiToggle | None = None
    paste_into_isolated_page: RbiToggle | None = None
    popups: RbiToggle | None = None
    printing: RbiToggle | None = None
    readonly: RbiToggle | None = None
    private_navigation: RbiToggle | None = None
    third_party_inspection: RbiThirdPartyInspection | None = None
    watermark: RbiToggle | None = None


class RbiTemplate(NetskopeModel):
    metadata: RbiTemplateMetadata = Field(alias="template_metadata")
    settings: RbiTemplateSettings | None = Field(None, alias="template_data")
