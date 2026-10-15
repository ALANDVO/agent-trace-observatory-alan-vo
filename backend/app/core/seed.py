"""Seed initial demonstration traces."""
import json, time
from app.core.database import get_db, init_db
from app.services.cost_engine import cost_engine
from app.services.redaction import redaction_engine

def _s(sid, par, name, stype, stat, inp, out, lat, ptok, ctok, err=""):
    return {"span_id": sid, "parent_span_id": par, "span_name": name, "span_type": stype, "status": stat, "input_data": inp, "output_data": out, "latency_ms": lat, "prompt_tokens": ptok, "completion_tokens": ctok, "start_time": 1.0, "end_time": 1.0 + lat/1000, "error_message": err}

def _spans():
    return [
        {"trace_id":"trace-code-refactor-01","agent_name":"SoftwareRefactoringAgent","status":"completed","root_goal":"Refactor legacy authentication module and generate unit tests","model":"qwen3.8-27b","spans":[_s("sp-101",None,"ast_parse_repo","tool_call","success",'{"path":"legacy/auth.py"}','{"symbols":14}',78.4,1200,340),_s("sp-102","sp-101","generate_session_code","llm_inference","success",'{"prompt":"Migrate SessionStore"}','{"code":"class SecureStore:..."}',412,2800,920),_s("sp-103","sp-102","execute_pytest","tool_call","success",'{"test_path":"tests/test_auth.py"}','{"passed":18}',320.5,850,120)]},
        {"trace_id":"trace-retry-loop-02","agent_name":"WebScrapingResearcher","status":"failed","root_goal":"Extract latest research paper PDF","model":"gpt-4o","spans":[_s("sp-201",None,"browser_click","tool_call","error",'{"selector":"#download"}','{"error":"ElementNotFound"}',1020,1500,60,err="ElementNotFound"),_s("sp-202","sp-201","browser_click","tool_call","retrying",'{"selector":"#download","r":1}','{"error":"ElementNotFound"}',1015,1700,55,err="ElementNotFound"),_s("sp-203","sp-202","browser_click","tool_call","error",'{"selector":"#download","r":2}','{"error":"Recursion"}',1018,1900,50,err="Max retries")]},
        {"trace_id":"trace-sensitive-03","agent_name":"CloudDeploymentAuditor","status":"completed","root_goal":"Audit AWS IAM roles and secret store access","model":"claude-3-5-sonnet-20241022","spans":[_s("sp-301",None,"fetch_cloud_credentials","tool_call","success",'{"key":"AKIAIOSFODNN7EXAMPLE","req":"admin@enterprise.org"}','{"api_key":"sk-proj-99999999999999999999999999999999","token":"Bearer secret_prod_token_1234567890","ssn":"001-01-0001"}',210,2200,450),_s("sp-302","sp-301","publish_audit_report","tool_call","success",'{"channel":"#sec-ops","email":"security-lead@company.com"}','{"status":"published"}',85,950,110)]}
    ]

def seed_database() -> None:
    init_db()
    with get_db() as c:
        if c.execute("SELECT COUNT(*) FROM traces").fetchone()[0] > 0: return
    # Seed redaction rules
    with get_db() as c:
        if c.execute("SELECT COUNT(*) FROM redaction_rules WHERE is_builtin=0").fetchone()[0] == 0:
            now = time.time()
            for r in [
                ("internal-api-key",r"\bINT_API_[A-Z0-9]{24}\b","[REDACTED:INTERNAL_API_KEY]","SECRET_KEY"),
                ("custom-session-token",r"\bSESS_[a-zA-Z0-9_-]{32}\b","[REDACTED:CUSTOM_SESSION_TOKEN]","SECRET_KEY"),
                ("database-connection-string",r"(postgres|mysql|mongodb)://[^\s]+:[^\s@]+@[^\s]+","[REDACTED:DATABASE_CONNECTION]","SECRET_KEY"),
            ]:
                c.execute("INSERT INTO redaction_rules(rule_name,pattern,replacement,category,pattern_type,is_builtin,enabled,created_at,updated_at) VALUES(?,?,?,?,'regex',0,1,?,?)", (*r, now, now))
    now = time.time()
    for item in _spans():
        t_id, spans, model = item["trace_id"], item["spans"], item["model"]
        tp = sum(s["prompt_tokens"] for s in spans)
        tc = sum(s["completion_tokens"] for s in spans)
        cost = sum(cost_engine.calculate_span_cost(s["prompt_tokens"], s["completion_tokens"], model) for s in spans)
        dur = max(s["end_time"] for s in spans) - min(s["start_time"] for s in spans)
        errs = sum(1 for s in spans if s["status"] in ("error","retrying") or s.get("error_message"))
        reds, ps = 0, []
        for i, s in enumerate(spans):
            ri, mi = redaction_engine.redact_text(s["input_data"])
            ro, mo = redaction_engine.redact_text(s["output_data"])
            reds += len(mi) + len(mo)
            sc = cost_engine.calculate_span_cost(s["prompt_tokens"], s["completion_tokens"], model)
            ps.append((s["span_id"], t_id, s["parent_span_id"], s["span_name"], s["span_type"], model, s["input_data"], s["output_data"], ri, ro, s["status"], s.get("error_message",""), s["latency_ms"], s["prompt_tokens"], s["completion_tokens"], sc, s["start_time"], s["end_time"], i))
        with get_db() as c:
            c.execute("""INSERT INTO traces VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (t_id, item["agent_name"], item["status"], item["root_goal"], model, tp+tc, tp, tc, round(cost,6), round(dur,3), len(spans), len(spans), errs, reds, now, now, json.dumps({"seeded":True})))
            c.executemany("""INSERT INTO spans VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", ps)