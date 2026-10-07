"""Tests for API endpoints, role-based authorization, CSRF enforcement, and LLM adapters."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.core.security import Role, create_session
from app.main import app


@pytest.mark.asyncio
async def test_healthcheck(async_client: AsyncClient):
    """Verify healthcheck endpoint returns healthy status and service metadata."""
    resp = await async_client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "agent-trace-observatory-alan-vo"


@pytest.mark.asyncio
async def test_unauthenticated_rejection_when_demo_disabled():
    """Verify 401 Unauthorized rejection when demo mode is disabled and no credentials provided."""
    with patch.object(settings, "demo_mode", False):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/traces")
            assert resp.status_code == 401
            assert "Authentication required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_role_denial_viewer_cannot_import(viewer_session):
    """Verify 403 Forbidden when a viewer attempts to import traces."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        payload = {
            "agent_name": "TestAgent",
            "root_goal": "Goal",
            "spans": []
        }
        resp = await client.post("/api/traces", json=payload, headers={"X-CSRF-Token": viewer_session.csrf_token})
        assert resp.status_code == 403
        assert "Requires role 'analyst'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_role_denial_analyst_cannot_delete(analyst_session):
    """Verify 403 Forbidden when an analyst attempts to delete traces."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": analyst_session.session_id}
    ) as client:
        resp = await client.delete("/api/traces/some-trace-id", headers={"X-CSRF-Token": analyst_session.csrf_token})
        assert resp.status_code == 403
        assert "Requires role 'admin'" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trace_import_redaction_and_retrieval(analyst_session, viewer_session):
    """Verify complete trace import workflow: automated secret redaction, token accounting, and detail retrieval."""
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": analyst_session.session_id}
    ) as client:
        payload = {
            "trace_id": "test-trace-api-01",
            "agent_name": "APITestAgent",
            "root_goal": "Validate API endpoints and redaction pipeline",
            "model": "qwen3.8-27b",
            "spans": [
                {
                    "span_id": "s-api-1",
                    "span_name": "fetch_data",
                    "span_type": "tool_call",
                    "input_data": '{"api_key": "sk-proj-123456789012345678901234", "user": "alice@company.com"}',
                    "output_data": '{"token": "Bearer testtoken1234567890123456", "status": "ok"}',
                    "status": "success",
                    "latency_ms": 150.0,
                    "prompt_tokens": 500,
                    "completion_tokens": 150,
                    "start_time": 100.0,
                    "end_time": 100.15
                }
            ]
        }

        import_resp = await client.post("/api/traces", json=payload, headers={"X-CSRF-Token": analyst_session.csrf_token})
        assert import_resp.status_code == 201
        data = import_resp.json()
        assert data["summary"]["trace_id"] == "test-trace-api-01"
        assert data["summary"]["redactions_count"] >= 2
        assert "[REDACTED:OPENAI_KEY]" in data["spans"][0]["redacted_input"]
        assert "[REDACTED:BEARER_TOKEN]" in data["spans"][0]["redacted_output"]

    # Retrieve with viewer session
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        detail_resp = await client.get("/api/traces/test-trace-api-01")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["dag"]["trace_id"] == "test-trace-api-01"
        assert len(detail["dag"]["nodes"]) == 1
        assert detail["failure_analysis"]["primary_failure"] == "HEALTHY_EXECUTION"


@pytest.mark.asyncio
async def test_trace_filtering_and_pagination(viewer_session):
    """Verify trace query filtering by agent name, search query, and pagination."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        resp = await client.get("/api/traces?limit=10&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["limit"] == 10


@pytest.mark.asyncio
async def test_trace_export_json_and_csv(viewer_session):
    """Verify trace exports in both JSON and CSV formats."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        # JSON export
        resp_json = await client.get("/api/export/traces?format=json")
        assert resp_json.status_code == 200
        assert isinstance(resp_json.json(), list)

        # CSV export
        resp_csv = await client.get("/api/export/traces?format=csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["content-type"]
        assert "trace_id,agent_name,status" in resp_csv.text


@pytest.mark.asyncio
async def test_evaluation_run_endpoint(analyst_session):
    """Verify triggering evaluation benchmark via REST API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": analyst_session.session_id}
    ) as client:
        resp = await client.post("/api/evaluation/run", headers={"X-CSRF-Token": analyst_session.csrf_token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["accuracy"] >= 0.90
        assert data["dataset_name"] == "agent-trace-benchmark-v1"
        assert len(data["metrics"]) == 4


@pytest.mark.asyncio
async def test_analytics_overview_endpoint(viewer_session):
    """Verify aggregate analytics overview metrics calculation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        resp = await client.get("/api/analytics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_traces" in data
        assert "overall_failure_rate" in data
        assert "failure_distribution" in data


@pytest.mark.asyncio
async def test_advisory_llm_offline_fallback(admin_session, viewer_session):
    """Verify grounded advisory LLM endpoint produces deterministic report when LLM_API_KEY is unset."""
    with patch.object(settings, "llm_api_key", None):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
            cookies={"session_id": admin_session.session_id}
        ) as client:
            # Seed a trace first
            payload = {
                "trace_id": "test-trace-advisory-01",
                "agent_name": "AdvisoryTestAgent",
                "root_goal": "Test offline advisory report",
                "spans": [
                    {
                        "span_id": "s1",
                        "span_name": "failing_step",
                        "span_type": "tool_call",
                        "status": "error",
                        "error_message": "429: Too Many Requests",
                        "start_time": 1.0,
                        "end_time": 1.1
                    }
                ]
            }
            create_resp = await client.post("/api/traces", json=payload, headers={"X-CSRF-Token": admin_session.csrf_token})
            assert create_resp.status_code == 201

            resp = await client.post(
                "/api/traces/test-trace-advisory-01/advisory",
                json={"custom_prompt": "Explain this trace"},
                headers={"X-CSRF-Token": admin_session.csrf_token}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_offline_fallback"] is True
            assert "Offline Deterministic Core" in data["explanation_markdown"]
            assert len(data["grounded_evidence"]) > 0


@pytest.mark.asyncio
async def test_audit_logs_export_admin_only(admin_session, viewer_session):
    """Verify audit logs are accessible by administrator and denied to viewer."""
    transport = ASGITransport(app=app)

    # Viewer denied
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": viewer_session.session_id}
    ) as client:
        resp_denied = await client.get("/api/export/audit-logs")
        assert resp_denied.status_code == 403

    # Admin allowed
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        cookies={"session_id": admin_session.session_id}
    ) as client:
        resp_allowed = await client.get("/api/export/audit-logs")
        assert resp_allowed.status_code == 200
        assert isinstance(resp_allowed.json(), list)
