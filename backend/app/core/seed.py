"""Seed initial demonstration traces into SQLite persistence."""

import json
import time
from app.core.database import get_db, init_db
from app.services.cost_engine import cost_engine
from app.services.redaction import redaction_engine


def _s(sid, par, name, stype, stat, inp, out, lat, ptok, ctok, err=""):
    return {"span_id": sid, "parent_span_id": par, "span_name": name, "span_type": stype, "status": stat, "input_data": inp, "output_data": out, "latency_ms": lat, "prompt_tokens": ptok, "completion_tokens": ctok, "start_time": 1.0, "end_time": 1.0 + (lat / 1000.0), "error_message": err}


def _make_seed_spans():
    return [
        {
            "trace_id": "trace-code-refactor-01", "agent_name": "SoftwareRefactoringAgent", "status": "completed",
            "root_goal": "Refactor legacy authentication module and generate unit tests", "model": "qwen3.8-27b",
            "spans": [
                _s("sp-101", None, "ast_parse_repo", "tool_call", "success", '{"path": "legacy/auth.py"}', '{"symbols": 14}', 78.4, 1200, 340),
                _s("sp-102", "sp-101", "generate_session_code", "llm_inference", "success", '{"prompt": "Migrate SessionStore"}', '{"code": "class SecureStore: ..."}', 412.0, 2800, 920),
                _s("sp-103", "sp-102", "execute_pytest", "tool_call", "success", '{"test_path": "tests/test_auth.py"}', '{"passed": 18}', 320.5, 850, 120)
            ]
        },
        {
            "trace_id": "trace-retry-loop-oscillation-02", "agent_name": "WebScrapingResearcher", "status": "failed",
            "root_goal": "Extract latest research paper PDF from portal", "model": "gpt-4o",
            "spans": [
                _s("sp-201", None, "browser_click", "tool_call", "error", '{"selector": "#download"}', '{"error": "ElementNotFound"}', 1020.0, 1500, 60, err="ElementNotFound: Button not visible"),
                _s("sp-202", "sp-201", "browser_click", "tool_call", "retrying", '{"selector": "#download", "r": 1}', '{"error": "ElementNotFound"}', 1015.0, 1700, 55, err="ElementNotFound: Button not visible"),
                _s("sp-203", "sp-202", "browser_click", "tool_call", "error", '{"selector": "#download", "r": 2}', '{"error": "Recursion"}', 1018.0, 1900, 50, err="Recursion limit: max retries exceeded in retry loop")
            ]
        },
        {
            "trace_id": "trace-sensitive-leak-blocked-03", "agent_name": "CloudDeploymentAuditor", "status": "completed",
            "root_goal": "Audit AWS IAM roles and secret store access", "model": "claude-3-5-sonnet-20241022",
            "spans": [
                _s("sp-301", None, "fetch_cloud_credentials", "tool_call", "success", '{"key": "AKIAIOSFODNN7EXAMPLE", "req": "admin@enterprise.org"}', '{"api_key": "sk-proj-99999999999999999999999999999999", "token": "Bearer secret_prod_token_1234567890", "ssn": "001-01-0001"}', 210.0, 2200, 450),
                _s("sp-302", "sp-301", "publish_audit_report", "tool_call", "success", '{"channel": "#sec-ops", "email": "security-lead@company.com"}', '{"status": "published"}', 85.0, 950, 110)
            ]
        }
    ]


def seed_database() -> None:
    """Insert initial demonstration traces if database is currently empty."""
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM traces")
        if cursor.fetchone()[0] > 0:
            return

    now = time.time()
    for item in _make_seed_spans():
        t_id, spans, model = item["trace_id"], item["spans"], item["model"]
        total_p = sum(s["prompt_tokens"] for s in spans)
        total_c = sum(s["completion_tokens"] for s in spans)
        cost = sum(cost_engine.calculate_span_cost(s["prompt_tokens"], s["completion_tokens"], model) for s in spans)
        dur = max(s["end_time"] for s in spans) - min(s["start_time"] for s in spans)
        errs = sum(1 for s in spans if s["status"] in ("error", "retrying") or s.get("error_message"))

        redacts = 0
        proc_spans = []
        for idx, s in enumerate(spans):
            r_in, m_in = redaction_engine.redact_text(s["input_data"])
            r_out, m_out = redaction_engine.redact_text(s["output_data"])
            redacts += len(m_in) + len(m_out)
            s_cost = cost_engine.calculate_span_cost(s["prompt_tokens"], s["completion_tokens"], model)
            proc_spans.append((
                s["span_id"], t_id, s["parent_span_id"], s["span_name"], s["span_type"], model,
                s["input_data"], s["output_data"], r_in, r_out, s["status"],
                s.get("error_message", ""), s["latency_ms"], s["prompt_tokens"], s["completion_tokens"],
                s_cost, s["start_time"], s["end_time"], idx
            ))

        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT INTO traces VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (t_id, item["agent_name"], item["status"], item["root_goal"], model,
                 total_p + total_c, total_p, total_c, round(cost, 6), round(dur, 3),
                 len(spans), len(spans), errs, redacts, now, now, json.dumps({"seeded": True}))
            )
            c.executemany(
                """INSERT INTO spans VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                proc_spans
            )
