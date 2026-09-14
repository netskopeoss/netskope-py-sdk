"""Shared fixtures and helpers for resource unit tests.

Provides context-managed sync/async clients pointed at a dummy tenant, plus
small helpers for inspecting mocked requests and draining paginators:

- ``client`` / ``aclient`` fixtures — pre-built clients (respx intercepts at
  send time, so building the client before the mock activates is fine).
- ``contract_client`` / ``contract_aclient`` — the same, against a host that
  resolves nowhere and with retries off, for tests that pin a request against
  the published gateway contract.
- ``retrying_client`` / ``retrying_aclient`` — that host with a retry budget,
  so a replay the SDK opts out of is observable.
- ``example_client`` / ``example_aclient`` — the ``example.goskope.com`` host
  the contract's own examples use.
- ``sent_json(route)`` / ``sent_params(route)`` — body and query string of
  the last request on a route.
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

# The contract tests point at a tenant that resolves to no real host, so a
# request escaping respx fails instead of leaving the machine. It is not a
# recognised Netskope domain, hence ``allow_custom_tenant``.
CONTRACT_TENANT = "example.goskope.coken"
CONTRACT_BASE = f"https://{CONTRACT_TENANT}"

# The host the contract's own request and response examples are written against.
EXAMPLE_TENANT = "example.goskope.com"
EXAMPLE_BASE = f"https://{EXAMPLE_TENANT}"


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


@pytest.fixture
def contract_client() -> Iterator[NetskopeClient]:
    """A sync client against the synthetic host, with retries off.

    Retries are off so a test that counts requests is measuring the call the
    SDK chose to make, not the transport's recovery from a mocked failure.
    """
    with NetskopeClient(
        tenant=CONTRACT_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=0,
    ) as c:
        yield c


@pytest.fixture
async def contract_aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """The async twin of :func:`contract_client`."""
    async with AsyncNetskopeClient(
        tenant=CONTRACT_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=0,
    ) as c:
        yield c


@pytest.fixture
def retrying_client() -> Iterator[NetskopeClient]:
    """A sync client with a retry budget, so an opt-out of replay is visible.

    ``backoff_factor=0`` keeps the retries instant: the tests assert how many
    requests were made, never how long they took.
    """
    with NetskopeClient(
        tenant=CONTRACT_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=2,
        backoff_factor=0.0,
    ) as c:
        yield c


@pytest.fixture
async def retrying_aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """The async twin of :func:`retrying_client`."""
    async with AsyncNetskopeClient(
        tenant=CONTRACT_TENANT,
        api_token="synthetic-token",
        allow_custom_tenant=True,
        max_retries=2,
        backoff_factor=0.0,
    ) as c:
        yield c


@pytest.fixture
def example_client() -> Iterator[NetskopeClient]:
    """A sync client against the host the contract's examples use."""
    with NetskopeClient(tenant=EXAMPLE_TENANT, api_token="tok") as c:
        yield c


@pytest.fixture
async def example_aclient() -> AsyncIterator[AsyncNetskopeClient]:
    """The async twin of :func:`example_client`."""
    async with AsyncNetskopeClient(tenant=EXAMPLE_TENANT, api_token="tok") as c:
        yield c


def contract_router(**kwargs: Any) -> respx.Router:
    """A router that fails the test if the SDK sends a request it did not declare.

    ``assert_all_called`` is off because several checks assert a route is
    *never* reached; those assert their own ``call_count``.
    """
    kwargs.setdefault("base_url", CONTRACT_BASE)
    return respx.mock(assert_all_mocked=True, assert_all_called=False, **kwargs)


def sent_params(route: respx.Route) -> dict[str, str]:
    """Return the query string of the last request captured by *route*."""
    return dict(route.calls.last.request.url.params)


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
