"""Aggregate analytics and observatory dashboard metrics."""

from collections import defaultdict
from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.security import Role, UserSession, require_role
from app.models.schemas import AggregateStatsResponse, FailurePatternType
from app.services.dag_builder import dag_builder
from app.services.failure_analyzer import failure_analyzer

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AggregateStatsResponse)
async def get_overview(user: UserSession = Depends(require_role(Role.VIEWER))):
    """Compute aggregate observability statistics across all stored agent traces."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Query all traces
        cursor.execute("SELECT * FROM traces")
        traces = cursor.fetchall()

        # Query all spans
        cursor.execute("SELECT * FROM spans")
        spans = cursor.fetchall()

    total_traces = len(traces)
    if total_traces == 0:
        return AggregateStatsResponse(
            total_traces=0,
            successful_traces=0,
            failed_traces=0,
            overall_failure_rate=0.0,
            total_tokens_processed=0,
            total_cost_usd=0.0,
            avg_latency_seconds=0.0,
            total_redactions=0,
            failure_distribution={},
            top_failing_tools=[],
            model_cost_distribution={}
        )

    successful = sum(1 for t in traces if t["status"] == "completed" and t["error_count"] == 0)
    failed = total_traces - successful
    failure_rate = round(failed / total_traces, 4)

    total_tokens = sum(t["total_tokens"] for t in traces)
    total_cost = round(sum(t["total_cost_usd"] for t in traces), 5)
    avg_latency = round(sum(t["duration_seconds"] for t in traces) / total_traces, 2)
    total_redactions = sum(t["redactions_count"] for t in traces)

    # Cost distribution by model
    model_costs: Dict[str, float] = defaultdict(float)
    for t in traces:
        m = t["model"] or "unknown"
        model_costs[m] += float(t["total_cost_usd"])
    model_cost_dist = {k: round(v, 4) for k, v in model_costs.items()}

    # Failure distribution by deterministic pattern
    spans_by_trace: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in spans:
        spans_by_trace[s["trace_id"]].append(dict(s))

    failure_dist: Dict[str, int] = defaultdict(int)
    for t in traces:
        t_id = t["trace_id"]
        t_spans = spans_by_trace.get(t_id, [])
        dag = dag_builder.build_dag(t_id, t_spans)
        analysis = failure_analyzer.analyze_trace(
            dict(t), t_spans, dag.has_cycles, dag.retry_loops_detected, t["redactions_count"]
        )
        failure_dist[analysis.primary_failure.value] += 1

    # Tool failure leaderboard
    tool_counts: Dict[str, int] = defaultdict(int)
    tool_failures: Dict[str, int] = defaultdict(int)

    for s in spans:
        if s["span_type"] == "tool_call":
            t_name = s["span_name"]
            tool_counts[t_name] += 1
            if s["status"] in ("error", "retrying") or bool(s["error_message"]):
                tool_failures[t_name] += 1

    top_failing_tools = []
    for tool_name, fail_count in sorted(tool_failures.items(), key=lambda x: x[1], reverse=True)[:5]:
        total_invocations = tool_counts.get(tool_name, 1)
        top_failing_tools.append({
            "tool_name": tool_name,
            "failure_count": fail_count,
            "total_calls": total_invocations,
            "error_rate": round(fail_count / total_invocations, 3)
        })

    return AggregateStatsResponse(
        total_traces=total_traces,
        successful_traces=successful,
        failed_traces=failed,
        overall_failure_rate=failure_rate,
        total_tokens_processed=total_tokens,
        total_cost_usd=total_cost,
        avg_latency_seconds=avg_latency,
        total_redactions=total_redactions,
        failure_distribution=dict(failure_dist),
        top_failing_tools=top_failing_tools,
        model_cost_distribution=model_cost_dist
    )
