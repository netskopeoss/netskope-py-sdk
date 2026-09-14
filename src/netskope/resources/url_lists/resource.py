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
from typing import Any

from netskope.core.pagination import AsyncPaginatedResponse, SyncPaginatedResponse
from netskope.core.resource import AsyncResource, SyncResource
from netskope.models.url_lists import UrlList
from netskope.resources.url_lists.decoder import AsyncUrlListResponses, UrlListResponses
from netskope.resources.url_lists.paths import (
    _DEPLOY_PATH,
    _PATH,
    _build_list_params,
    _flatten_url_list,
    _list_path,
    _merge_source,
    _payload,
    _require_record,
    _update_fields,
)

# The only deploy operation the gateway declares for URL lists is
# ``POST /urllist/deploy`` (policy/urllist.yaml:201-227); there is no bare
# ``/policy/deploy`` path anywhere in the spec.

# ``GET /urllist`` accepts ``pending`` (0 or 1) and ``field`` — singular, one
# value — and nothing else (policy/urllist.yaml:133-156).

# A record carries its own identity or its payload; an envelope carries neither,
# so a record whose ``data`` came back empty is still recognized by ``id``/``name``.


# The fields the API requires on every PUT, so a merge cannot silently drop them.


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


class UrlListsResource(SyncResource):
    """Synchronous interface to ``/api/v2/policy/urllist``."""

    @cached_property
    def with_response(self) -> UrlListResponses:
        """Opt into bounded typed responses with their original wire values."""

        return UrlListResponses(self._transport)

    def list(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        page_size: int = 100,
    ) -> SyncPaginatedResponse[UrlList]:
        """List all URL lists.

        Note:
            ``GET /urllist`` declares exactly two query parameters, ``pending``
            and ``field`` (``policy/urllist.yaml:132-156``), and returns a bare
            array with no total (``:157-165``).  With no ``offset`` or ``limit``
            to send, the whole collection arrives in one request and is
            iterated from there; *page_size* is accepted for signature
            compatibility and is not sent.

        Args:
            pending: ``1`` for lists with undeployed changes, ``0`` for
                applied lists (``policy/urllist.yaml:133-142``).
            field: Return only this field of each record — one of ``id``,
                ``name``, ``data``, ``modify_type``, ``modify_time``,
                ``modify_by``, ``pending`` (``:143-156``).
            page_size: Unused; the operation declares no ``limit``.

        Returns:
            A lazy iterator of :class:`~netskope.models.url_lists.UrlList` over
            the one collection response.

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
            paginated=False,
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

        return AsyncUrlListResponses(self._transport)

    def list(
        self,
        *,
        pending: int | bool | None = None,
        field: str | None = None,
        page_size: int = 100,
    ) -> AsyncPaginatedResponse[UrlList]:
        """List all URL lists.  See :meth:`UrlListsResource.list`."""
        return AsyncPaginatedResponse(
            transport=self._transport,
            method="GET",
            path=_PATH,
            params=_build_list_params(pending, field),
            model=UrlList,
            page_size=page_size,
            extract=_extract,
            paginated=False,
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
