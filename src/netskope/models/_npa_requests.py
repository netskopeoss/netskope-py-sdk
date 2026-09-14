"""Validation shared by NPA request models, separate from permissive responses."""

from __future__ import annotations

from typing import Any, ClassVar, Self, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic import ValidationError as ModelValidationError

from netskope.exceptions import ValidationError

T = TypeVar("T", bound=BaseModel)


class NpaRequest(BaseModel):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        populate_by_name=True,
        revalidate_instances="always",
    )

    @model_validator(mode="after")
    def reject_unsupported_nulls(self) -> Self:
        for name in self.model_fields_set - self.nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} does not accept an explicit null.")
        return self


def request_payload(request: T | dict[str, Any], model: type[T]) -> dict[str, Any]:
    """Revalidate nested mutable values at the HTTP request boundary.

    *request* is either a request model or the field mapping a legacy keyword
    signature collected, so both paths serialize through the same contract.
    """
    try:
        validated = model.model_validate(request)
    except ModelValidationError as exc:
        locations = ", ".join(".".join(map(str, item["loc"])) or "request" for item in exc.errors())
        raise ValidationError(f"Invalid NPA request fields: {locations}.") from None
    return validated.model_dump(mode="json", by_alias=True, exclude_unset=True)
