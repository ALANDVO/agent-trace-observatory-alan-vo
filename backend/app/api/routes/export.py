"""Data export routes for JSON and CSV reporting."""

import csv
import io
import json
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Response

from app.core.database import get_db
from app.core.security import Role, UserSession, require_role
from app.services.redaction import redaction_engine

router = APIRouter(prefix="/export", tags=["export"])


def _trace_filter(
    agent_name: Optional[str],
    status_filter: Optional[str],
    model: Optional[str],
    has_errors: Optional[bool],
    min_cost: Optional[float],
    search: Optional[str],
) -> str:
    """Build the shared trace WHERE clause used by both listing and export."""
    clauses = ["1=1"]
    params: List[Any] = []
    if agent_name:
        clauses.append("agent_name = ?")
        params.append(agent_name)
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)
    if model:
        clauses.append("model LIKE ?")
        params.append(f"%{model}%")
    if has_errors is True:
        clauses.append("error_count > 0")
    elif has_errors is False:
        clauses.append("error_count = 0")
    if min_cost is not None:
        clauses.append("total_cost_usd >= ?")
        params.append(min_cost)
    if search:
        clauses.append("(agent_name LIKE ? OR root_goal LIKE ? OR trace_id LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    return " AND ".join(clauses), params


@router.get("/traces")
async def export_traces(
    format: str = Query("json", pattern="^(json|csv)$"),
    agent_name: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    model: Optional[str] = Query(None),
    has_errors: Optional[bool] = Query(None),
    min_cost: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserSession = Depends(require_role(Role.VIEWER))
):
    """Export stored agent trace records formatted as JSON or CSV.

    Applies the same filters as the trace list endpoint. Export rows are limited
    to ``limit`` records so a single request cannot dump unbounded history;
    callers page with ``offset``.
    """
    fieldnames = [
        "trace_id", "agent_name", "status", "model", "root_goal",
        "total_tokens", "prompt_tokens", "completion_tokens",
        "total_cost_usd", "duration_seconds", "step_count",
        "tool_call_count", "error_count", "redactions_count", "created_at"
    ]
    where_sql, params = _trace_filter(agent_name, status_filter, model, has_errors, min_cost, search)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM traces WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = cursor.fetchall()

        # Export text is re-sanitized on read: span payloads captured before a
        # custom redaction rule existed must not leave the system unredacted.
        spans: dict[str, list] = {}
        for row in rows:
            cursor.execute("SELECT input_data, output_data FROM spans WHERE trace_id=?", (row["trace_id"],))
            spans[row["trace_id"]] = [
                (s["input_data"], s["output_data"]) for s in cursor.fetchall()
            ]

    records: List[dict] = []
    for r in rows:
        record = {k: r[k] for k in fieldnames}
        record["metadata"] = json.loads(r["metadata_json"] or "{}")
        record["spans"] = []
        for input_data, output_data in spans[r["trace_id"]]:
            record["spans"].append({
                "input_data": redaction_engine.redact_text(input_data or "")[0],
                "output_data": redaction_engine.redact_text(output_data or "")[0],
            })
        records.append(record)

    if format == "csv":
        # Flat, deterministic CSV of trace aggregates only (span payloads are
        # multi-line free text and would corrupt row alignment).
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({k: record[k] for k in fieldnames})
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agent_traces_export.csv"})

    return records


@router.get("/audit-logs")
async def export_audit_logs(user: UserSession = Depends(require_role(Role.ADMIN))):
    """Retrieve system security audit trail (Administrator only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100")
        rows = cursor.fetchall()

    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "username": r["username"],
            "action": r["action"],
            "resource_type": r["resource_type"],
            "resource_id": r["resource_id"],
            "details": r["details"],
            "ip_address": r["ip_address"],
            "created_at": r["created_at"]
        }
        for r in rows
    ]
