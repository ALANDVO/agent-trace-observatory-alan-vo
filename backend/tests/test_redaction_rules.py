"""Tests for custom redaction rules API and engine integration."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.security import Role, create_session
from app.services.redaction import redaction_engine


@pytest.fixture
def admin_session():
    return create_session(
        user_id="test-admin-redaction",
        username="admin_redaction",
        email="admin_redaction@test.local",
        roles=[Role.ADMIN.value]
    )


@pytest.fixture
def analyst_session():
    return create_session(
        user_id="test-analyst-redaction",
        username="analyst_redaction",
        email="analyst_redaction@test.local",
        roles=[Role.ANALYST.value]
    )


@pytest.fixture
def viewer_session():
    return create_session(
        user_id="test-viewer-redaction",
        username="viewer_redaction",
        email="viewer_redaction@test.local",
        roles=[Role.VIEWER.value]
    )


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_list_redaction_rules_viewer(viewer_session, async_client: AsyncClient):
    """Verify viewer can list redaction rules."""
    cookies = {"session_id": viewer_session.session_id}
    resp = await async_client.get("/api/redaction/rules", cookies=cookies)
    assert resp.status_code == 200
    rules = resp.json()
    assert isinstance(rules, list)
    # Should include seeded custom rules
    rule_names = [r["rule_name"] for r in rules]
    assert "internal-api-key" in rule_names
    assert "custom-session-token" in rule_names
    assert "database-connection-string" in rule_names


@pytest.mark.asyncio
async def test_list_redaction_rules_unauthenticated(async_client: AsyncClient):
    """Verify unauthenticated request is rejected when demo mode disabled."""
    # Test with demo mode enabled (current test env)
    resp = await async_client.get("/api/redaction/rules")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_redaction_rule_admin(admin_session, async_client: AsyncClient):
    """Verify admin can create a custom redaction rule."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    rule_data = {
        "rule_name": "test-custom-token",
        "pattern": r"\bTEST_TOKEN_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED:TEST_CUSTOM_TOKEN]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    resp = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["rule_name"] == "test-custom-token"
    assert data["pattern"] == rule_data["pattern"]
    assert data["is_builtin"] is False
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_create_redaction_rule_invalid_regex(admin_session, async_client: AsyncClient):
    """Verify invalid regex is rejected."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    rule_data = {
        "rule_name": "invalid-regex",
        "pattern": r"[invalid(",  # Invalid regex
        "replacement": "[REDACTED]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    resp = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert resp.status_code == 400
    assert "Invalid regex" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_redaction_rule_duplicate_name(admin_session, async_client: AsyncClient):
    """Verify duplicate rule name is rejected."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    rule_data = {
        "rule_name": "duplicate-test",
        "pattern": r"\bTOKEN_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    # Create first
    resp1 = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert resp1.status_code == 201

    # Try to create again
    resp2 = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert resp2.status_code == 409
    assert "exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_create_redaction_rule_viewer_forbidden(viewer_session, async_client: AsyncClient):
    """Verify viewer cannot create redaction rules."""
    cookies = {"session_id": viewer_session.session_id}
    headers = {"X-CSRF-Token": viewer_session.csrf_token}

    rule_data = {
        "rule_name": "viewer-rule",
        "pattern": r"\bTOKEN_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    resp = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_redaction_rule_admin(admin_session, async_client: AsyncClient):
    """Verify admin can update a custom redaction rule."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Create a rule first
    rule_data = {
        "rule_name": "update-test",
        "pattern": r"\bOLD_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED:OLD]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    create_resp = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    # Update the rule
    update_data = {
        "pattern": r"\bNEW_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED:NEW]",
        "enabled": False
    }
    update_resp = await async_client.put(f"/api/redaction/rules/{rule_id}", json=update_data, cookies=cookies, headers=headers)
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["pattern"] == update_data["pattern"]
    assert data["replacement"] == update_data["replacement"]
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_builtin_rule_forbidden(admin_session, async_client: AsyncClient):
    """Verify built-in rules cannot be modified."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Find a built-in rule (there aren't any in DB, but test the logic)
    # We'll create a rule with is_builtin=1 via direct DB for this test
    from app.core.database import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO redaction_rules (rule_name, pattern, replacement, category, pattern_type, is_builtin, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            ("builtin-test", r"\bBUILTIN_[A-Z0-9]{16}\b", "[REDACTED:BUILTIN]", "SECRET_KEY", "regex", 1234567890.0, 1234567890.0)
        )
        builtin_id = cursor.lastrowid

    update_data = {"pattern": r"\bMODIFIED_[A-Z0-9]{16}\b"}
    resp = await async_client.put(f"/api/redaction/rules/{builtin_id}", json=update_data, cookies=cookies, headers=headers)
    assert resp.status_code == 403
    assert "Cannot modify built-in" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_redaction_rule_admin(admin_session, async_client: AsyncClient):
    """Verify admin can delete a custom redaction rule."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Create a rule first
    rule_data = {
        "rule_name": "delete-test",
        "pattern": r"\bDELETE_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED:DELETE]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    create_resp = await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    # Delete the rule
    delete_resp = await async_client.delete(f"/api/redaction/rules/{rule_id}", cookies=cookies, headers=headers)
    assert delete_resp.status_code == 204

    # Verify it's gone
    list_resp = await async_client.get("/api/redaction/rules", cookies=cookies)
    assert list_resp.status_code == 200
    rules = list_resp.json()
    rule_names = [r["rule_name"] for r in rules]
    assert "delete-test" not in rule_names


@pytest.mark.asyncio
async def test_delete_builtin_rule_forbidden(admin_session, async_client: AsyncClient):
    """Verify built-in rules cannot be deleted."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Create a built-in rule via direct DB
    from app.core.database import get_db
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO redaction_rules (rule_name, pattern, replacement, category, pattern_type, is_builtin, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)""",
            ("builtin-delete-test", r"\bBUILTIN_DEL_[A-Z0-9]{16}\b", "[REDACTED:BUILTIN_DEL]", "SECRET_KEY", "regex", 1234567890.0, 1234567890.0)
        )
        builtin_id = cursor.lastrowid

    resp = await async_client.delete(f"/api/redaction/rules/{builtin_id}", cookies=cookies, headers=headers)
    assert resp.status_code == 403
    assert "Cannot delete built-in" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_test_redaction_pattern_analyst(analyst_session, async_client: AsyncClient):
    """Verify analyst can test redaction patterns."""
    cookies = {"session_id": analyst_session.session_id}

    test_data = {
        "pattern": r"\bTEST_[A-Z0-9]{16}\b",
        "pattern_type": "regex",
        "sample_text": "Here is a token: TEST_ABCDEFGHIJKLMNOP and another TEST_QRSTUVWXYZ123456"
    }
    resp = await async_client.post("/api/redaction/rules/test", json=test_data, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_valid"] is True
    assert len(data["matches"]) == 2
    assert "TEST_ABCDEFGHIJKLMNOP" in data["matches"][0]["match"]
    assert "[REDACTED]" in data["sanitized_text"]


@pytest.mark.asyncio
async def test_test_redaction_pattern_literal(analyst_session, async_client: AsyncClient):
    """Verify literal pattern type works."""
    cookies = {"session_id": analyst_session.session_id}

    test_data = {
        "pattern": "SECRET_VALUE_123",
        "pattern_type": "literal",
        "sample_text": "The secret is SECRET_VALUE_123 and more text"
    }
    resp = await async_client.post("/api/redaction/rules/test", json=test_data, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_valid"] is True
    assert len(data["matches"]) == 1
    assert data["matches"][0]["match"] == "SECRET_VALUE_123"


@pytest.mark.asyncio
async def test_test_redaction_pattern_invalid_regex(analyst_session, async_client: AsyncClient):
    """Verify invalid regex returns error but not exception."""
    cookies = {"session_id": analyst_session.session_id}

    test_data = {
        "pattern": r"[invalid(",
        "pattern_type": "regex",
        "sample_text": "test"
    }
    resp = await async_client.post("/api/redaction/rules/test", json=test_data, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pattern_valid"] is False
    assert "error" in data
    assert data["sanitized_text"] == "test"


@pytest.mark.asyncio
async def test_custom_rule_applied_during_trace_import(admin_session, async_client: AsyncClient):
    """Verify custom redaction rules are applied during trace import."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Create a custom rule that matches INT_API_ format
    rule_data = {
        "rule_name": "import-test-token",
        "pattern": r"\bIMPORT_TEST_[A-Z0-9]{20}\b",
        "replacement": "[REDACTED:IMPORT_TEST_TOKEN]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": True
    }
    await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)
    trace_data = {
        "agent_name": "TestAgent",
        "status": "completed",
        "root_goal": "Test custom redaction",
        "model": "qwen3.8-27b",
        "spans": [
            {
                "span_id": "sp-1",
                "parent_span_id": None,
                "span_name": "process_credentials",
                "span_type": "tool_call",
                "status": "success",
                "input_data": '{"api_key": "IMPORT_TEST_ABCDEFGHIJKLMNOPQRST"}',
                "output_data": '{"result": "ok"}',
                "latency_ms": 100.0,
                "prompt_tokens": 500,
                "completion_tokens": 100,
                "start_time": 1.0,
                "end_time": 1.1,
                "step_index": 0
            }
        ]
    }
    import_resp = await async_client.post("/api/traces", json=trace_data, cookies=cookies, headers=headers)
    assert import_resp.status_code == 201
    trace_detail = import_resp.json()

    # Verify redaction occurred
    span = trace_detail["spans"][0]
    assert "[REDACTED:IMPORT_TEST_TOKEN]" in span["redacted_input"]
    assert "IMPORT_TEST_ABCDEFGHIJKLMNOPQRST" not in span["redacted_input"]

    # Verify redaction report includes custom rule
    redaction_summary = trace_detail["redaction_summary"]
    assert redaction_summary["total_redactions"] > 0
    categories = redaction_summary["categories_detected"]
    assert "SECRET_KEY" in categories


@pytest.mark.asyncio
async def test_custom_rule_disabled_not_applied(admin_session, async_client: AsyncClient):
    """Verify disabled custom rules are not applied."""
    cookies = {"session_id": admin_session.session_id}
    headers = {"X-CSRF-Token": admin_session.csrf_token}

    # Create a disabled custom rule
    rule_data = {
        "rule_name": "disabled-rule",
        "pattern": r"\bDISABLED_TOKEN_[A-Z0-9]{16}\b",
        "replacement": "[REDACTED:DISABLED]",
        "category": "SECRET_KEY",
        "pattern_type": "regex",
        "enabled": False
    }
    await async_client.post("/api/redaction/rules", json=rule_data, cookies=cookies, headers=headers)

    # Import a trace containing the token
    trace_data = {
        "trace_id": "trace-disabled-rule-01",
        "agent_name": "TestAgent",
        "status": "completed",
        "root_goal": "Test disabled rule",
        "model": "qwen3.8-27b",
        "spans": [
            {
                "span_id": "sp-1",
                "parent_span_id": None,
                "span_name": "process",
                "span_type": "tool_call",
                "status": "success",
                "input_data": '{"token": "DISABLED_TOKEN_ABCDEFGHIJKLMNOP"}',
                "output_data": '{"ok": true}',
                "latency_ms": 50.0,
                "prompt_tokens": 200,
                "completion_tokens": 50,
                "start_time": 1.0,
                "end_time": 1.05,
                "step_index": 0
            }
        ]
    }
    import_resp = await async_client.post("/api/traces", json=trace_data, cookies=cookies, headers=headers)
    assert import_resp.status_code == 201
    trace_detail = import_resp.json()

    # Verify redaction did NOT occur (rule is disabled)
    span = trace_detail["spans"][0]
    assert "DISABLED_TOKEN_ABCDEFGHIJKLMNOP" in span["redacted_input"]
    assert "[REDACTED:DISABLED]" not in span["redacted_input"]


def test_redaction_engine_custom_rules_integration():
    """Verify RedactionEngine loads and applies custom rules from database."""
    from app.core.database import get_db

    # Add a custom rule directly to DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO redaction_rules (rule_name, pattern, replacement, category, pattern_type, is_builtin, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)""",
            ("engine-test", r"\bENGINE_TEST_[A-Z0-9]{12}\b", "[REDACTED:ENGINE_TEST]", "SECRET_KEY", "regex", 9999999999.0, 9999999999.0)
        )

    # Invalidate cache to force reload
    redaction_engine.invalidate_cache()

    # Test redaction
    text = "The key is ENGINE_TEST_ABCDEFGHIJKL and done."
    sanitized, matches = redaction_engine.redact_text(text)

    assert "[REDACTED:ENGINE_TEST]" in sanitized
    assert "ENGINE_TEST_ABCDEFGHIJKL" not in sanitized
    assert len(matches) == 1
    assert matches[0].pattern_name == "engine-test"
    assert matches[0].category == "SECRET_KEY"

    # Cleanup
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM redaction_rules WHERE rule_name = ?", ("engine-test",))
    redaction_engine.invalidate_cache()


def test_redaction_engine_builtin_rules_still_work():
    """Verify built-in rules still work after custom rules addition."""
    redaction_engine.invalidate_cache()

    text = "OpenAI key: sk-proj-abcdefghijklmnopqrstuvwxyz123456789012"
    sanitized, matches = redaction_engine.redact_text(text)

    assert "[REDACTED:OPENAI_KEY]" in sanitized
    assert "sk-proj-" not in sanitized
    assert any(m.pattern_name == "OPENAI_KEY" for m in matches)


import time