"""Live integration tests for the Client Enrollment token set API.

Follows the safety checklist in ``tests/integration/conftest.py``: test
objects use the ``sdk-inttest-`` prefix, every create has a guaranteed
delete, and unavailable APIs skip rather than fail.

``client.enrollment`` is not wired into the client yet, so tests build an
``EnrollmentResource`` directly on the client's transport.
"""

from __future__ import annotations

import contextlib

import pytest

from netskope import NetskopeClient
from netskope.exceptions import APIError, NotFoundError
from netskope.models.enrollment import EnrollmentTokenSet
from netskope.resources.enrollment import EnrollmentResource

from .conftest import skip_if_unavailable, unique_name


@pytest.fixture
def enrollment(client: NetskopeClient) -> EnrollmentResource:
    return EnrollmentResource(client._transport)


@pytest.mark.integration
class TestEnrollmentIntegration:
    """Live tests for enrollment token sets."""

    def test_list_token_sets(self, enrollment: EnrollmentResource) -> None:
        """Read smoke: listing token sets succeeds and yields typed models.

        The API answers 404 when the tenant has no token sets at all;
        ``skip_if_unavailable`` treats that as a skip, not a failure.
        """
        try:
            token_sets = enrollment.list_token_sets(limit=10)
        except APIError as e:
            skip_if_unavailable(e, "Enrollment token sets")
        else:
            assert isinstance(token_sets, list)
            if token_sets:
                assert isinstance(token_sets[0], EnrollmentTokenSet)
                assert token_sets[0].id is not None

    def test_token_set_write_cycle(self, enrollment: EnrollmentResource) -> None:
        """Create → list contains it → delete an enrollment token set."""
        name = unique_name("enroll")
        try:
            created = enrollment.create_token_set(name)
        except APIError as e:
            skip_if_unavailable(e, "Enrollment token sets")
            return
        assert created.id is not None
        try:
            token_sets = enrollment.list_token_sets()
            assert any(ts.id == created.id for ts in token_sets)
        finally:
            with contextlib.suppress(NotFoundError):
                enrollment.delete_token_set(created.id)
