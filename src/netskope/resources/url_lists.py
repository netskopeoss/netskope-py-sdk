"""URL Lists resource — manage URL allow/block lists and deploy policy.

Example::

    # List all URL lists
    for url_list in client.url_lists.list():
        print(f"{url_list.name}: {len(url_list.urls)} entries")

    # Create a new blocklist
    new_list = client.url_lists.create(
        name="threat-iocs",
        urls=["malware.example.com", "phishing.bad.org"],
        list_type="exact",
    )

    # Apply every pending URL-list change
    client.url_lists.deploy()
"""

from __future__ import annotations

import builtins
from functools import cached_property
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from netskope.resources._url_list_response import AsyncUrlListResponses, UrlListResponses

from netskope._pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.exceptions import ResponseValidationError, ValidationError
from netskope.models.url_lists import UrlList
from netskope.resources._base import AsyncResource, SyncResource
from netskope.resources._extract import validate_id

_PATH = "/api/v2/policy/urllist"

# The only deploy operation the gateway declares for URL lists is
# ``POST /urllist/deploy`` (policy/urllist.yaml:201-227); there is no bare
# ``/policy/deploy`` path anywhere in the spec.
_DEPLOY_PATH = f"{_PATH}/deploy"

# ``GET /urllist`` accepts ``pending`` (0 or 1) and ``field`` — singular, one
# value — and nothing else (policy/urllist.yaml:133-156).
_LIST_FIELDS = ("id", "name", "data", "modify_type", "modify_time", "modify_by", "pending")

# A record carries its own identity or its payload; an envelope carries neither,
# so a record whose ``data`` came back empty is still recognized by ``id``/``name``.
_RECORD_KEYS = frozenset({"id", "name", "urls", "type"})

_LIST_TYPES = ("exact", "regex")

# The fields the API requires on every PUT, so a merge cannot silently drop them.
_REQUIRED_ON_UPDATE = frozenset({"name", "urls", "type"})


def _flatten_url_list(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested 'data' key into the top-level item dict."""
    if "data" in item and isinstance(item["data"], dict):
        flat = {**item}
        inner = flat.pop("data")
        flat.update(inner)
        return flat
    return item


def _extract(body: Any) -> list[dict[str, Any]]:
    """Extract URL list items, handling both list and dict envelopes."""
    items: list[dict[str, Any]] = []
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        data = body.get("data", [])
        if isinstance(data, dict):
            urllists = data.get("urllists", [])
            items = urllists if isinstance(urllists, list) else [data]
        elif isinstance(data, list):
            items = data
    return [_flatten_url_list(item) for item in items if isinstance(item, dict)]


def _single(items: builtins.list[Any]) -> dict[str, Any]:
    return items[0] if len(items) == 1 and isinstance(items[0], dict) else {}


def _is_record(candidate: dict[str, Any]) -> bool:
    """Whether a dict is a URL list itself rather than an envelope around one."""
    return bool(_RECORD_KEYS & candidate.keys())


def _as_record(candidate: dict[str, Any]) -> dict[str, Any]:
    """Flatten one candidate into a record, or state that it is not one."""
    flat = _flatten_url_list(candidate)
    return flat if _is_record(flat) else {}


def _extract_one(body: Any) -> dict[str, Any]:
    """Extract a single URL list item from any of the response shapes the API returns.

    POST returns ``[{...}]`` while GET/PUT return the bare record, ``{"data":
    {...}}``, ``{"data": [{...}]}``, or a ``urllists`` collection nested under
    ``data`` or at the top level.  :func:`_flatten_url_list` merges a record's
    nested payload up.  An empty dict means no single record was found;
    :func:`_require_record` turns that into an error.
    """
    if isinstance(body, list):
        return _as_record(_single(body))
    if not isinstance(body, dict):
        return {}
    if _is_record(body):
        return _as_record(body)
    data = body.get("data")
    if isinstance(data, list):
        return _as_record(_single(data))
    nested = data.get("urllists") if isinstance(data, dict) else None
    for collection in (nested, body.get("urllists")):
        if isinstance(collection, list):
            return _as_record(_single(collection))
    return _as_record(data) if isinstance(data, dict) else {}


def _require_record(
    body: Any,
    *,
    request_method: str | None = None,
    request_path: str | None = None,
) -> dict[str, Any]:
    """Return the single URL list in *body*, refusing an absent or ambiguous record."""
    record = _extract_one(body)
    if not record:
        raise ResponseValidationError(
            "The response did not contain exactly one URL list.",
            request_method=request_method,
            request_path=request_path,
        )
    return record


def _list_path(list_id: int) -> str:
    """Build the single-list path, rejecting an identifier that could alter it."""
    return f"{_PATH}/{validate_id(list_id, 'list_id')}"


def _merge_source(current: UrlList, list_id: int) -> UrlList:
    """Reject a read that cannot safely seed the full-body PUT ``update`` sends.

    ``UrlList.urls`` defaults to an empty list, so an unrecognized envelope would
    otherwise merge into a PUT that erases every URL in the list.
    """
    missing = _REQUIRED_ON_UPDATE - current.model_fields_set
    if missing:
        raise ResponseValidationError(
            f"The URL list read did not return {', '.join(sorted(missing))}; "
            "refusing to build an update from it.",
            request_method="GET",
            request_path=_list_path(list_id),
        )
    if str(current.id) != str(list_id):
        raise ResponseValidationError(
            "The URL list read identifies a different list.",
            request_method="GET",
            request_path=_list_path(list_id),
        )
    return current


def _payload(name: str, urls: builtins.list[str], list_type: str) -> dict[str, Any]:
    """Validate the caller's fields and build the body the API requires.

    ``name`` sits at the top level; ``urls`` and ``type`` are wrapped in ``data``.
    """
    if list_type not in _LIST_TYPES:
        raise ValidationError(f"list_type must be one of: {', '.join(_LIST_TYPES)}.")
    if (
        not isinstance(name, str)
        or not isinstance(urls, list)
        or any(not isinstance(url, str) for url in urls)
    ):
        raise ValidationError("URL lists require a name and a list of URL strings.")
    return {"name": name, "data": {"urls": list(urls), "type": list_type}}


def _build_list_params(pending: int | bool | None, field: str | None) -> dict[str, Any]:
    """Validate and build the two query parameters ``GET /urllist`` declares."""
    params: dict[str, Any] = {}
    if pending is not None:
        if isinstance(pending, bool):
            pending = int(pending)
        if pending not in (0, 1):
            raise ValidationError("pending must be 0 (applied) or 1 (pending).")
        params["pending"] = pending
    if field is not None:
        if field not in _LIST_FIELDS:
            raise ValidationError(f"field must be one of: {', '.join(_LIST_FIELDS)}.")
        params["field"] = field
    return params


def _update_fields(
    name: str | None,
    urls: builtins.list[str] | None,
    list_type: str | None,
) -> None:
    """Reject an update with nothing to change or with values the API refuses."""
    if name is None and urls is None and list_type is None:
        raise ValidationError("Provide name, urls, or list_type to update a URL list.")
    _payload(
        name if name is not None else "",
        urls if urls is not None else [],
        list_type if list_type is not None else "exact",
    )


class UrlListsResource(SyncResource):
    """Synchronous interface to ``/api/v2/policy/urllist``."""

    @cached_property
    def with_response(self) -> UrlListResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._url_list_response import UrlListResponses

        return UrlListResponses(self._transport)

    def list(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[UrlList]:
        """List all URL lists with automatic pagination.

        Note:
            ``GET /urllist`` returns a bare array with no total
            (``policy/urllist.yaml:157-165``) and declares no ``limit`` or
            ``offset``; the paginator still sends them, so a tenant that
            ignores them answers the whole collection on the first page.

        Args:
            pending: ``1`` for lists with undeployed changes, ``0`` for
                applied lists (``policy/urllist.yaml:133-142``).
            field: Return only this field of each record — one of ``id``,
                ``name``, ``data``, ``modify_type``, ``modify_time``,
                ``modify_by``, ``pending`` (``:143-156``).
            page_size: Results per page.

        Returns:
            A lazy paginated iterator of :class:`~netskope.models.url_lists.UrlList`.

        Raises:
            netskope.exceptions.ValidationError: If *pending* or *field* is
                not a value the API accepts.
        """
        return SyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(pending, field),
            model=UrlList,
            page_size=page_size,
            extract=_extract,
        )

    def get(self, list_id: int) -> UrlList:
        """Get a URL list by ID.

        Args:
            list_id: The numeric URL list identifier.

        Returns:
            A :class:`~netskope.models.url_lists.UrlList` instance.

        Raises:
            netskope.exceptions.ValidationError: If *list_id* is unsafe to
                interpolate into the request path.
            netskope.exceptions.ResponseValidationError: If the response does
                not carry exactly one URL list.
        """
        path = _list_path(list_id)
        body = self._get(path)
        return UrlList.model_validate(
            _require_record(body, request_method="GET", request_path=path)
        )

    def create(
        self,
        name: str,
        urls: builtins.list[str],
        *,
        list_type: str = "exact",
    ) -> UrlList:
        """Create a new URL list.

        Args:
            name: Human-readable name for the list.
            urls: The URLs to include.
            list_type: Matching strategy (``"exact"`` or ``"regex"``).

        Returns:
            The newly created :class:`~netskope.models.url_lists.UrlList`.

        Raises:
            netskope.exceptions.ValidationError: If *name*, *urls*, or
                *list_type* is not a value the API accepts.
            netskope.exceptions.ResponseValidationError: If the response does
                not carry exactly one URL list.
        """
        body = self._post(_PATH, json=_payload(name, urls, list_type))
        return UrlList.model_validate(
            _require_record(body, request_method="POST", request_path=_PATH)
        )

    def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: builtins.list[str] | None = None,
        list_type: str | None = None,
    ) -> UrlList:
        """Update an existing URL list.

        The Netskope API requires ``name``, ``data.urls``, and ``data.type`` on every
        PUT request, so this method GETs the current list first and merges the provided
        fields over the existing values. Callers only need to supply what they want to
        change. At least one of ``name``, ``urls``, or ``list_type`` must be provided.

        Args:
            list_id: The URL list identifier.
            name: New name (optional).
            urls: New URL entries (optional).
            list_type: New matching strategy (optional).

        Returns:
            The updated :class:`~netskope.models.url_lists.UrlList`.

        Raises:
            netskope.exceptions.ValidationError: If no field was provided, or a
                provided field is not a value the API accepts.
            netskope.exceptions.ResponseValidationError: If the current list
                cannot be read back in full, so merging would erase fields.
        """
        _update_fields(name, urls, list_type)
        path = _list_path(list_id)
        current = _merge_source(self.get(list_id), list_id)
        body = self._put(
            path,
            json=_payload(
                name if name is not None else (current.name or ""),
                urls if urls is not None else list(current.urls),
                list_type if list_type is not None else (current.type or "exact"),
            ),
        )
        return UrlList.model_validate(
            _require_record(body, request_method="PUT", request_path=path)
        )

    def delete(self, list_id: int) -> None:
        """Delete a URL list.

        Args:
            list_id: The URL list identifier.
        """
        self._delete(_list_path(list_id))

    def deploy(self) -> dict[str, Any]:
        """Apply every pending URL-list change (``POST /urllist/deploy``).

        Returns:
            The deployment result: the API answers with the array of URL lists
            it applied (``policy/urllist.yaml:209-217``).
        """
        return self._post(_DEPLOY_PATH)


class AsyncUrlListsResource(AsyncResource):
    """Asynchronous interface to ``/api/v2/policy/urllist``."""

    @cached_property
    def with_response(self) -> AsyncUrlListResponses:
        """Opt into bounded typed responses with their original wire values."""
        from netskope.resources._url_list_response import AsyncUrlListResponses

        return AsyncUrlListResponses(self._transport)

    def list(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[UrlList]:
        """List all URL lists with automatic pagination.

        See :meth:`UrlListsResource.list`.
        """
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(pending, field),
            model=UrlList,
            page_size=page_size,
            extract=_extract,
        )

    async def get(self, list_id: int) -> UrlList:
        """Get a URL list by ID.

        See :meth:`UrlListsResource.get`.
        """
        path = _list_path(list_id)
        body = await self._get(path)
        return UrlList.model_validate(
            _require_record(body, request_method="GET", request_path=path)
        )

    async def create(
        self,
        name: str,
        urls: builtins.list[str],
        *,
        list_type: str = "exact",
    ) -> UrlList:
        """Create a new URL list.

        See :meth:`UrlListsResource.create`.
        """
        body = await self._post(_PATH, json=_payload(name, urls, list_type))
        return UrlList.model_validate(
            _require_record(body, request_method="POST", request_path=_PATH)
        )

    async def update(
        self,
        list_id: int,
        *,
        name: str | None = None,
        urls: builtins.list[str] | None = None,
        list_type: str | None = None,
    ) -> UrlList:
        """Update an existing URL list.

        The API requires ``name``, ``data.urls``, and ``data.type`` on every PUT, so
        this method GETs the current list first and merges the provided fields over
        the existing values. At least one of ``name``, ``urls``, or ``list_type`` must
        be provided.  See :meth:`UrlListsResource.update`.
        """
        _update_fields(name, urls, list_type)
        path = _list_path(list_id)
        current = _merge_source(await self.get(list_id), list_id)
        body = await self._put(
            path,
            json=_payload(
                name if name is not None else (current.name or ""),
                urls if urls is not None else list(current.urls),
                list_type if list_type is not None else (current.type or "exact"),
            ),
        )
        return UrlList.model_validate(
            _require_record(body, request_method="PUT", request_path=path)
        )

    async def delete(self, list_id: int) -> None:
        """Delete a URL list."""
        await self._delete(_list_path(list_id))

    async def deploy(self) -> dict[str, Any]:
        """Apply every pending URL-list change.  See :meth:`UrlListsResource.deploy`."""
        return await self._post(_DEPLOY_PATH)
