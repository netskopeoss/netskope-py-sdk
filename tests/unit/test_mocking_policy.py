"""The unit suite cannot reach a live tenant.

``tests/conftest.py`` installs a router with ``assert_all_mocked=True`` around
every test, so a request no test declared raises instead of leaving the
process. This pins that guarantee, which the contract tests depend on.
"""

from __future__ import annotations

import respx


def test_the_mock_router_refuses_an_unmocked_request() -> None:
    """No test here can reach a live tenant: an undeclared request is an error."""
    assert respx.mock._assert_all_mocked is True
