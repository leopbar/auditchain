"""Shared pytest fixtures for all test levels.

Unit tests: no DB required — use raw data from disk.
Integration tests: require a running PostgreSQL instance (auditchain-postgres).
"""

import pytest
from auditchain.data.database import get_session


@pytest.fixture
def db_session():
    """Yield a live database session for integration tests.

    Requires the auditchain-postgres container to be running.
    Each test gets a fresh session; changes are NOT rolled back automatically
    (integration tests operate against real data after ingestion).
    """
    with get_session() as session:
        yield session
