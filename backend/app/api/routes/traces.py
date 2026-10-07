"""Trace ingestion, listing, detail inspection, and advisory analysis routes."""

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.database import get_db, log_audit_event
from app.core.security import Role, UserSession, get_current_user, require_role
from app.models.schemas import (
    AdvisoryLLMRequest,
    AdvisoryLLMResponse,
    RedactionMatch,
    SpanResponse,
    TraceDetailResponse,
    TraceImportRequest,
    TraceListResponse,
    TraceStatus,
    TraceSummaryResponse
)
from app.services.cost_engine import cost_engine
from app.services.dag_builder import dag_builder
from app.services.failure_analyzer import failure_analyzer
from app.services.llm_client import llm_client
from app.services.redaction import redaction_engine

router = APIRouter(prefix="/traces", tags=["traces"])


def _to_summary(r) -> TraceSummaryResponse:
    d = dict(r)
    d["status"] = TraceStatus(d["status"])
    return TraceSummaryResponse(**d)


def _to_span(s) -> SpanResponse:
    d = dict(s)
    return SpanResponse(**d)


@router.get("", response_model=TraceListResponse)
async def list_traces(
    agent_name: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    model: Optional[str] = Query(None),
    has_errors: Optional[bool] = Query(None),
    min_cost: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserSession = Depends(require_role(Role.VIEWER))
):
    """Retrieve paginated agent traces with multi-criteria filtering."""
    clauses = ["1=1"]
    params: List[Any] = []
    if agent_name: clauses.append("agent_name = ?"); params.append(agent_name)
    if status_filter: clauses.append("status = ?"); params.append(status_filter)
    if model: clauses.append("model LIKE ?"); params.append(f"%{model}%")
    if has_errors is True: clauses.append("error_count > 0")
    elif has_errors is False: clauses.append("error_count = 0")
    if min_cost is not None: clauses.append("total_cost_usd >= ?"); params.append(min_cost)
    if search:
        clauses.append("(agent_name LIKE ? OR root_goal LIKE ? OR trace_id LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    where_sql = " AND ".join(clauses)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM traces WHERE {where_sql}", params)
        total = cursor.fetchone()[0]
        cursor.execute(f"SELECT * FROM traces WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?", params + [limit, offset])
        rows = cursor.fetchall()

    return TraceListResponse(items=[_to_summary(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=TraceDetailResponse, status_code=status.HTTP_201_CREATED)
async def import_trace(
    payload: TraceImportRequest,
    request: Request,
    user: UserSession = Depends(require_role(Role.ANALYST))
):
    """Import a structured execution trace with automated secret redaction and cost calculation."""
    trace_id = payload.trace_id or f"trace-{uuid.uuid4().hex[:12]}"
    now = time.time()

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    tool_call_count = 0
    error_count = 0
    total_redactions = 0
    all_redaction_matches: List[RedactionMatch] = []

    processed_spans: List[Dict[str, Any]] = []

    # Process and sanitize each span
    for idx, s in enumerate(payload.spans):
        # Redact input and output data
        redacted_input, in_matches = redaction_engine.redact_text(s.input_data)
        redacted_output, out_matches = redaction_engine.redact_text(s.output_data)

        span_redactions = len(in_matches) + len(out_matches)
        total_redactions += span_redactions
        all_redaction_matches.extend(in_matches + out_matches)

        span_model = s.model or payload.model
        cost = cost_engine.calculate_span_cost(s.prompt_tokens, s.completion_tokens, span_model)

        total_prompt_tokens += s.prompt_tokens
        total_completion_tokens += s.completion_tokens
        total_cost += cost

        if s.span_type.value == "tool_call":
            tool_call_count += 1

        if s.status.value in ("error", "retrying") or bool(s.error_message):
            error_count += 1

        processed_spans.append((
            s.span_id or f"span-{idx + 1}-{uuid.uuid4().hex[:6]}", trace_id, s.parent_span_id, s.span_name,
            s.span_type.value, span_model, s.input_data, s.output_data, redacted_input, redacted_output,
            s.status.value, s.error_message, s.latency_ms, s.prompt_tokens, s.completion_tokens,
            cost, s.start_time, s.end_time, s.step_index or idx
        ))

    duration_sec = max(max(s.end_time for s in payload.spans) - min(s.start_time for s in payload.spans), 0.0) if payload.spans else 0.0
    total_tokens = total_prompt_tokens + total_completion_tokens
    final_status = TraceStatus.FAILED.value if error_count > 0 and payload.status.value == TraceStatus.COMPLETED.value else payload.status.value

    # Persist in SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO traces (
                trace_id, agent_name, status, root_goal, model,
                total_tokens, prompt_tokens, completion_tokens,
                total_cost_usd, duration_seconds, step_count, tool_call_count,
                error_count, redactions_count, created_at, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace_id, payload.agent_name, final_status, payload.root_goal, payload.model,
                total_tokens, total_prompt_tokens, total_completion_tokens,
                round(total_cost, 6), round(duration_sec, 3), len(payload.spans),
                tool_call_count, error_count, total_redactions, now, now, json.dumps(payload.metadata)
            )
        )
        cursor.executemany(
            """INSERT OR REPLACE INTO spans (
                span_id, trace_id, parent_span_id, span_name, span_type, model,
                input_data, output_data, redacted_input, redacted_output,
                status, error_message, latency_ms, prompt_tokens, completion_tokens,
                cost_usd, start_time, end_time, step_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            processed_spans
        )

    log_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="IMPORT_TRACE",
        resource_type="trace",
        resource_id=trace_id,
        details=f"Imported trace with {len(processed_spans)} spans and {total_redactions} redactions.",
        ip_address=request.client.host if request.client else ""
    )

    return await get_trace(trace_id, user)


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: str,
    user: UserSession = Depends(require_role(Role.VIEWER))
):
    """Retrieve full trace details, execution DAG, failure diagnosis, and redaction stats."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,))
        t_row = cursor.fetchone()
        if not t_row:
            raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")

        cursor.execute("SELECT * FROM spans WHERE trace_id = ? ORDER BY step_index ASC, start_time ASC", (trace_id,))
        s_rows = cursor.fetchall()

    summary = _to_summary(t_row)
    spans_data = [dict(s) for s in s_rows]
    dag = dag_builder.build_dag(trace_id, spans_data)
    failure_analysis = failure_analyzer.analyze_trace(
        dict(t_row), spans_data, dag.has_cycles, dag.retry_loops_detected, t_row["redactions_count"]
    )

    all_matches: List[RedactionMatch] = []
    for s in spans_data:
        _, m_in = redaction_engine.redact_text(s.get("input_data", ""))
        _, m_out = redaction_engine.redact_text(s.get("output_data", ""))
        all_matches.extend(m_in + m_out)

    redaction_summary = redaction_engine.generate_report(all_matches)
    span_models = [_to_span(s) for s in s_rows]

    return TraceDetailResponse(
        summary=summary,
        spans=span_models,
        dag=dag,
        failure_analysis=failure_analysis,
        redaction_summary=redaction_summary,
        metadata=json.loads(t_row["metadata_json"] or "{}")
    )


@router.delete("/{trace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trace(
    trace_id: str,
    request: Request,
    user: UserSession = Depends(require_role(Role.ADMIN))
):
    """Delete a trace and all associated spans (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM traces WHERE trace_id = ?", (trace_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")
        cursor.execute("DELETE FROM traces WHERE trace_id = ?", (trace_id,))

    log_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="DELETE_TRACE",
        resource_type="trace",
        resource_id=trace_id,
        details="Trace deleted by administrator.",
        ip_address=request.client.host if request.client else ""
    )
    return None


@router.post("/{trace_id}/advisory", response_model=AdvisoryLLMResponse)
async def get_advisory_explanation(
    trace_id: str,
    payload: AdvisoryLLMRequest,
    user: UserSession = Depends(require_role(Role.VIEWER))
):
    """Generate grounded LLM advisory explanation for trace execution and failures."""
    detail = await get_trace(trace_id, user)
    spans_dicts = [s.model_dump() for s in detail.spans]

    return await llm_client.generate_trace_explanation(
        summary=detail.summary,
        analysis=detail.failure_analysis,
        spans=spans_dicts,
        custom_prompt=payload.custom_prompt
    )
