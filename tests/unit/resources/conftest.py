"""Shared fixtures and helpers for resource unit tests.

Provides context-managed sync/async clients pointed at a dummy tenant, plus
small helpers for inspecting mocked requests and draining paginators:

- ``client`` / ``aclient`` fixtures — pre-built clients (respx intercepts at
  send time, so building the client before the mock activates is fine).
- ``sent_json(route)`` — parsed JSON body of the last request on a route.
- ``drain(paginated)`` — collect all items from a sync or async paginator
  (coroutine: call it from async tests; sync tests can just use ``list()``).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import respx

from netskope import AsyncNetskopeClient, NetskopeClient


@pytest.fixture
def client() -> Iterator[NetskopeClient]:
    """A sync client against the dummy tenant, closed after the test."""
    with NetskopeClient(tenant="t.goskope.com", api_token="tok") as c:
        yield c


@pytest.fixture
async def aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """An async client against the dummy tenant, closed after the test."""
    async with AsyncNetskopeClient(tenant="t.goskope.com", api_token="tok") as c:
        yield c


def sent_json(route: respx.Route) -> Any:
    """Return the parsed JSON body of the last request captured by *route*."""
    return json.loads(route.calls.last.request.content)


async def drain(paginated: Any) -> list[Any]:
    """Collect every item from a sync or async paginated response.

    Works for both paginator flavors: sync paginators are drained with
    ``list()``, async ones with an async comprehension.  Await it from an
    async test (``asyncio_mode=auto``); plain sync tests can simply call
    ``list(response)`` directly.
    """
    if hasattr(paginated, "__aiter__"):
        return [item async for item in paginated]
    return list(paginated)
