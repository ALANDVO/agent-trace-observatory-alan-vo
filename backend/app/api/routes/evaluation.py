"""AI/ML benchmark evaluation routes and reproducibility endpoints."""

import json
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request

from app.core.database import get_db, log_audit_event
from app.core.security import Role, UserSession, require_role
from app.models.schemas import EvaluationRunResponse
from app.services.evaluator import BENCHMARK_DATASET, EvaluationSuite

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunResponse)
async def run_evaluation(
    request: Request,
    user: UserSession = Depends(require_role(Role.ANALYST))
):
    """Trigger reproducible benchmark evaluation across the labeled agent trace dataset."""
    result = EvaluationSuite.run_benchmark()

    # Persist evaluation run
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO evaluation_runs (
                run_id, dataset_name, sample_count, accuracy, loop_detection_f1,
                redaction_recall, cost_mae, failure_cls_f1, executed_at, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id, result.dataset_name, result.sample_count, result.accuracy,
                result.loop_detection_f1, result.redaction_recall, result.cost_estimation_mae,
                result.failure_classification_f1, result.executed_at,
                json.dumps([m.model_dump() for m in result.metrics])
            )
        )

    log_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="RUN_EVALUATION",
        resource_type="evaluation_run",
        resource_id=result.run_id,
        details=f"Ran benchmark on {result.sample_count} traces with accuracy {result.accuracy * 100:.1f}%.",
        ip_address=request.client.host if request.client else ""
    )

    return result


@router.get("/runs", response_model=List[Dict[str, Any]])
async def list_evaluation_runs(user: UserSession = Depends(require_role(Role.VIEWER))):
    """Retrieve historical evaluation runs and benchmark performance metrics."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evaluation_runs ORDER BY executed_at DESC LIMIT 20")
        rows = cursor.fetchall()

    return [
        {
            "run_id": r["run_id"],
            "dataset_name": r["dataset_name"],
            "sample_count": r["sample_count"],
            "accuracy": r["accuracy"],
            "loop_detection_f1": r["loop_detection_f1"],
            "redaction_recall": r["redaction_recall"],
            "cost_mae": r["cost_mae"],
            "failure_cls_f1": r["failure_cls_f1"],
            "executed_at": r["executed_at"],
            "metrics": json.loads(r["metrics_json"])
        }
        for r in rows
    ]


@router.get("/dataset")
async def get_benchmark_dataset(user: UserSession = Depends(require_role(Role.VIEWER))):
    """Inspect curated labeled dataset used for model and trace evaluator benchmarking."""
    summary_items = []
    for item in BENCHMARK_DATASET:
        summary_items.append({
            "trace_id": item["trace_id"],
            "agent_name": item["agent_name"],
            "expected_failure": item["expected_failure"].value,
            "expected_cycles": item["expected_cycles"],
            "expected_redactions": item["expected_redactions"],
            "spans_count": len(item["spans"])
        })
    return {"dataset_name": "agent-trace-benchmark-v1", "total_samples": len(summary_items), "samples": summary_items}
