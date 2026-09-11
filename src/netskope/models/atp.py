"""Typed ATP submission and analysis contracts."""

from __future__ import annotations

import io
import zipfile
import zlib
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, field_validator, model_validator

from netskope.models.administration import AdminRequest
from netskope.models.common import NetskopeModel

_MAX_FILE_BYTES = 16_000_000


class AtpFileScan(AdminRequest):
    """An existing password-protected ZipCrypto archive, not a file to repackage.

    The sandbox accepts one exe/pdf/doc/xls/ppt/rtf member, encrypted with
    password 'infected'. Upload bytes and expanded member are capped at 16 MB.
    """

    filename: str = Field(min_length=1)
    content: bytes = Field(min_length=1, max_length=_MAX_FILE_BYTES, repr=False)
    scan_type: Literal["sandbox"] = "sandbox"

    @model_validator(mode="after")
    def _archive_contract(self) -> Self:
        if not self.filename.lower().endswith(".zip") or any(
            c in self.filename for c in ("/", "\\", "\r", "\n")
        ):
            raise ValueError("The upload filename must be a ZIP basename.")
        try:
            with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
                members = archive.infolist()
                if len(members) != 1 or members[0].is_dir():
                    raise ValueError("The ZIP must contain exactly one file.")
                member = members[0]
                suffix = member.filename.rsplit(".", 1)[-1].lower()
                if suffix not in ("exe", "pdf", "doc", "xls", "ppt", "rtf"):
                    raise ValueError("The ZIP member type is not supported by the sandbox.")
                if not member.flag_bits & 1 or member.compress_type not in (
                    zipfile.ZIP_STORED,
                    zipfile.ZIP_DEFLATED,
                ):
                    raise ValueError("Use ZipCrypto encryption with password 'infected'.")
                if member.file_size > _MAX_FILE_BYTES:
                    raise ValueError("The expanded file exceeds the 16 MB sandbox limit.")
                with archive.open(member, pwd=b"infected") as stream:
                    if len(stream.read(_MAX_FILE_BYTES + 1)) > _MAX_FILE_BYTES:
                        raise ValueError("The expanded file exceeds the 16 MB sandbox limit.")
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error):
            raise ValueError("Use a valid ZipCrypto ZIP with password 'infected'.") from None
        return self


class AtpUrlScan(AdminRequest):
    url: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
        except ValueError:
            raise ValueError("Supply a valid HTTP or HTTPS URL.") from None
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Supply a complete HTTP or HTTPS URL.")
        return value


class AtpFileSubmission(NetskopeModel):
    job_id: str = Field(alias="jobid")
    status: str | None = None
    md5: str | None = None
    sha256: str | None = None
    requests_served: int | None = None


class AtpUrlSubmission(NetskopeModel):
    submission_id: str
    status: str | None = None
    message: str | None = None
    url_sha256: str | None = None


class AtpScanReport(NetskopeModel):
    """A sandbox report, with open forensic sections retained as JSON values."""

    job_id: str = Field(alias="jobid")
    status: str
    md5: str
    sha256: str
    requests_served: int
    verdict: str
    av_detection: dict[str, JsonValue] = Field(default_factory=dict)
    dropped: list[JsonValue] = Field(default_factory=list)
    network: dict[str, JsonValue] = Field(default_factory=dict)
    observed_behavior: dict[str, JsonValue] = Field(default_factory=dict)
    process_tree: list[JsonValue] = Field(default_factory=list)


class AtpSubmissionReport(NetskopeModel):
    """TPaaS report content and its already-encoded process-tree document."""

    report: dict[str, JsonValue]
    process_tree: str | None = Field(None, alias="processtree")
