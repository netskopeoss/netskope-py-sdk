"""Paths and payload builders shared by the publishers resource and its decoder.

Kept apart from both so the resource can import the decoder for its
``with_response`` accessor without the decoder importing the resource
back. This is the shape ``netskope/resources/shared/datasearch_query.py``
already uses.
"""

from __future__ import annotations

import builtins
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from netskope.core.ids import id_strings
from netskope.core.pagination import (
    Page,
    local_page,
)
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.publishers import (
    Publisher,
    PublisherCreate,
    PublisherUpdate,
)

_PATH = "/api/v2/infrastructure/publishers"


_RELEASES_PATH = f"{_PATH}/releases"


_BULK_PATH = f"{_PATH}/bulk"


_ALERTS_CONFIG_PATH = f"{_PATH}/alertsconfiguration"


def _parse_publishers_page(body: Any, offset: int, limit: int | None) -> Page[Publisher]:
    """Decode publisher records and window them locally, retaining envelope metadata.

    ``getNPAPublishers`` declares no ``offset`` or ``limit``
    (``npa_publishers.yaml:1024-1032``), so the response is the whole collection
    and any requested window is applied here; see :func:`local_page`.
    """
    metadata: dict[str, Any] = {}
    if isinstance(body, list):
        records = body
    elif isinstance(body, dict):
        metadata = dict(body)
        if isinstance(body.get("result"), list):
            records = metadata.pop("result")
        elif isinstance(body.get("data"), list):
            records = metadata.pop("data")
        elif isinstance(body.get("data"), dict) and "publishers" in body["data"]:
            nested = dict(body["data"])
            records = nested.pop("publishers")
            if nested:
                metadata["data"] = nested
            else:
                metadata.pop("data")
        elif "publishers" in body:
            records = metadata.pop("publishers")
        elif isinstance(body.get("Resources"), list):
            records = metadata.pop("Resources")
        else:
            raise ResponseValidationError(
                "Invalid publishers response: expected a publisher collection."
            )
    else:
        raise ResponseValidationError("Invalid publishers response: expected an object or list.")

    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ResponseValidationError(
            "Invalid publishers response: expected a list of publisher objects."
        )
    items = [Publisher.model_validate(item) for item in records]
    return local_page(items, metadata, offset, limit)


def _extract_publisher(body: dict[str, Any]) -> Publisher:
    if not isinstance(body, dict):
        raise ResponseValidationError("Invalid publisher response: expected a publisher object.")
    data = body.get("data", body)
    if isinstance(data, dict) and "publishers" in data:
        items = data["publishers"]
        if not isinstance(items, list) or len(items) != 1:
            raise ResponseValidationError(
                "Invalid publisher response: expected one publisher object."
            )
        data = items[0]
    if not isinstance(data, dict) or not data:
        raise ResponseValidationError("Invalid publisher response: expected a publisher object.")
    return Publisher.model_validate(data)


def _extract_token(body: dict[str, Any]) -> str:
    if not isinstance(body, dict):
        raise ResponseValidationError("Registration token missing from response.")
    data = body.get("data")
    if isinstance(data, dict) and data.get("token") is not None:
        return str(data["token"])
    if body.get("token") is not None:
        return str(body["token"])
    raise ResponseValidationError("Registration token missing from response.")


def _build_list_params(
    filter_expr: str | None,
    fields: builtins.list[str] | None,
) -> dict[str, Any]:
    """Build the one query parameter ``getNPAPublishers`` declares.

    ``fields`` is the whole declared query for this operation
    (``npa_publishers.yaml:1024-1032``): there is no ``filter``, ``offset`` or
    ``limit``. Rejecting *filter_expr* prevents a caller from relying on an
    undeclared server-side filter.
    """
    if filter_expr is not None:
        raise ValidationError(
            "filter_expr is not supported: GET /infrastructure/publishers declares only "
            "the 'fields' query parameter. Filter the "
            "returned records in Python instead."
        )
    params: dict[str, Any] = {}
    if fields:
        params["fields"] = ",".join(fields)
    return params


def _validate_window(offset: int | None, limit: int | None) -> None:
    """Reject a local paging window that could not describe a page of records."""
    for name, value, minimum in (("offset", offset, 0), ("limit", limit, 1)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValidationError(f"Invalid {name}: expected an integer >= {minimum}.")


_WIRE_NAMES = {"lbroker_connect": "lbrokerconnect"}


def _to_wire(payload: dict[str, Any]) -> dict[str, Any]:
    """Rename the fields whose gateway spelling differs from the SDK's."""
    return {_WIRE_NAMES.get(key, key): value for key, value in payload.items()}


def _validate_publisher_payload(
    payload: dict[str, Any],
    model: type[PublisherCreate] | type[PublisherUpdate],
) -> dict[str, Any]:
    known_fields = {key: value for key, value in payload.items() if key in model.model_fields}
    try:
        request = model.model_validate(known_fields)
    except PydanticValidationError as exc:
        # Name the fields, never `str(exc)`: pydantic renders the caller's own
        # input and a docs URL, which every sibling validator here strips.
        fields = ", ".join(".".join(map(str, error["loc"])) or "payload" for error in exc.errors())
        raise ValidationError(f"Invalid publisher request: {fields}.") from None
    return _to_wire({**payload, **request.model_dump(mode="json", exclude_unset=True)})


def _build_create_payload(
    name: str,
    lbroker_connect: bool,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "lbroker_connect": lbroker_connect}
    if extra_fields:
        payload.update(extra_fields)
    return _validate_publisher_payload(payload, PublisherCreate)


def _build_update_payload(
    name: str | None,
    extra_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the PATCH body, which the gateway declares ``name`` required on.

    ``publisher_patch_request`` declares ``required: [name]``
    (``npa_publishers.yaml:338-341``), so a body that changes only, say,
    ``lbrokerconnect`` is rejected on arrival. *name* may also arrive through
    *extra_fields*.
    """
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if extra_fields:
        payload.update(extra_fields)
    if payload.get("name") is None:
        raise ValidationError(
            "update() requires name: publisher_patch_request declares it required "
            "(npa_publishers.yaml:338-341)."
        )
    return _validate_publisher_payload(payload, PublisherUpdate)


def _build_bulk_upgrade_payload(publisher_ids: builtins.list[int | str]) -> dict[str, Any]:
    """Build the bulk-upgrade body, whose ids the gateway takes as strings.

    ``publishers_bulk_request.publishers.id.items`` is ``{type: string}``
    (npa_publishers.yaml:294-299), and the endpoint's own examples send
    ``["12"]`` (:1230-1244).  The sibling ``publisherupgradeprofiles/bulk``
    endpoint already sends strings.
    """
    if not isinstance(publisher_ids, list):
        raise ValidationError("publisher_ids must be a list of publisher IDs.")
    return {
        "publishers": {
            "apply": {"upgrade_request": True},
            "id": id_strings(publisher_ids, "publisher_ids"),
        }
    }
