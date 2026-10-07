"""Data export routes for JSON and CSV reporting."""

import csv
import io
import json
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Response

from app.core.database import get_db
from app.core.security import Role, UserSession, require_role

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/traces")
async def export_traces(
    format: str = Query("json", pattern="^(json|csv)$"),
    user: UserSession = Depends(require_role(Role.VIEWER))
):
    """Export stored agent trace records formatted as JSON or CSV."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM traces ORDER BY created_at DESC")
        rows = cursor.fetchall()

    if format == "csv":
        output = io.StringIO()
        fieldnames = [
            "trace_id", "agent_name", "status", "model", "root_goal",
            "total_tokens", "prompt_tokens", "completion_tokens",
            "total_cost_usd", "duration_seconds", "step_count",
            "tool_call_count", "error_count", "redactions_count", "created_at"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in fieldnames})
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agent_traces_export.csv"})

    return [{**{k: r[k] for k in fieldnames}, "metadata": json.loads(r["metadata_json"] or "{}")} for r in rows]


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
