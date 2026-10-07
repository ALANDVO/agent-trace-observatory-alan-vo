"""Pytest configuration, in-memory database fixtures, and test client."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = "./data/test_traces.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from app.core.config import settings
settings.database_url = f"sqlite:///{TEST_DB_PATH}"
settings.demo_mode = True

from app.core.database import get_db, init_db
from app.core.security import Role, create_session
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initialize fresh database schema and clear tables before each test."""
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM spans;")
        conn.execute("DELETE FROM traces;")
        conn.execute("DELETE FROM audit_logs;")
        conn.execute("DELETE FROM evaluation_runs;")
        conn.execute("DELETE FROM redaction_rules;")
    yield


@pytest.fixture
async def async_client():
    """Async HTTP test client for FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def admin_session():
    """Provision an authenticated admin session."""
    return create_session(
        user_id="test-admin-id",
        username="admin_user",
        email="admin@test.local",
        roles=[Role.ADMIN.value]
    )


@pytest.fixture
def analyst_session():
    """Provision an authenticated analyst session."""
    return create_session(
        user_id="test-analyst-id",
        username="analyst_user",
        email="analyst@test.local",
        roles=[Role.ANALYST.value]
    )


@pytest.fixture
def viewer_session():
    """Provision an authenticated viewer session."""
    return create_session(
        user_id="test-viewer-id",
        username="viewer_user",
        email="viewer@test.local",
        roles=[Role.VIEWER.value]
    )
