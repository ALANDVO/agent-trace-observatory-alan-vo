"""AI/ML agent trace evaluation benchmark suite with reproducible metrics and curated dataset."""

import json
import math
import sys
import time
import uuid
from typing import Any, Dict, List, Tuple
from app.models.schemas import (
    BenchmarkMetric,
    EvaluationRunResponse,
    FailurePatternType
)
from app.services.cost_engine import cost_engine
from app.services.dag_builder import dag_builder
from app.services.failure_analyzer import failure_analyzer
from app.services.redaction import redaction_engine


def _sp(sid: str, name: str, stype: str, status: str, p_tok: int, c_tok: int, lat: float, err: str = "", in_d: str = "", out_d: str = "", parent: str = None) -> Dict[str, Any]:
    return {
        "span_id": sid, "parent_span_id": parent, "span_name": name, "span_type": stype,
        "status": status, "error_message": err, "latency_ms": lat, "prompt_tokens": p_tok,
        "completion_tokens": c_tok, "input_data": in_d, "output_data": out_d, "start_time": 1.0, "end_time": 1.0 + (lat / 1000.0)
    }


def _item(tid: str, agent: str, fail_type: FailurePatternType, cyc: bool, red: int, spans: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"trace_id": tid, "agent_name": agent, "expected_failure": fail_type, "expected_cycles": cyc, "expected_redactions": red, "spans": spans}


BENCHMARK_DATASET: List[Dict[str, Any]] = [
    _item("eval-01-healthy", "AutonomousCodeGenerator", FailurePatternType.HEALTHY_EXECUTION, False, 0, [
        _sp("s1", "read_spec", "tool_call", "success", 1200, 300, 45.0),
        _sp("s2", "write_code", "tool_call", "success", 2500, 800, 120.0, parent="s1"),
        _sp("s3", "run_tests", "tool_call", "success", 1500, 200, 350.0, parent="s2")
    ]),
    _item("eval-02-context-overflow", "ResearchAgent", FailurePatternType.CONTEXT_OVERFLOW, False, 0, [
        _sp("s1", "query_vector_store", "tool_call", "success", 3000, 2000, 80.0),
        _sp("s2", "synthesize", "llm_inference", "error", 129000, 0, 25.0, err="Error 400: prompt too long, context length exceeded 128000 tokens", parent="s1")
    ]),
    _item("eval-03-rate-limit", "WebScraperAgent", FailurePatternType.RATE_LIMIT_EXCEEDED, False, 0, [
        _sp("s1", "fetch_page", "tool_call", "success", 800, 400, 150.0),
        _sp("s2", "parse_html", "tool_call", "error", 1000, 0, 50.0, err="HTTP 429 Too Many Requests: Rate limit exceeded, quota exceeded", parent="s1")
    ]),
    _item("eval-04-schema-val", "SqlSynthesizer", FailurePatternType.SCHEMA_VALIDATION_ERROR, False, 0, [
        _sp("s1", "gen_sql", "llm_inference", "success", 1500, 300, 200.0),
        _sp("s2", "exec_query", "tool_call", "error", 500, 0, 15.0, err="ValidationError: missing required field 'query' in JSON", parent="s1")
    ]),
    _item("eval-05-tool-failure", "DevOpsAssistant", FailurePatternType.TOOL_EXECUTION_FAILURE, False, 0, [
        _sp("s1", "check_status", "tool_call", "success", 600, 100, 40.0),
        _sp("s2", "run_cmd", "tool_call", "error", 700, 0, 30.0, err="CalledProcessError: command failed with exit code 127: docker not found", parent="s1")
    ]),
    _item("eval-06-retry-cycle", "BrowserAutomationAgent", FailurePatternType.RETRY_LOOP_EXHAUSTION, True, 0, [
        _sp("s1", "click_elem", "tool_call", "error", 1000, 50, 100.0, err="Element not found"),
        _sp("s2", "click_elem", "tool_call", "retrying", 1000, 50, 100.0, err="Element not found"),
        _sp("s3", "click_elem", "tool_call", "retrying", 1000, 50, 100.0, err="Element not found"),
        _sp("s4", "click_elem", "tool_call", "error", 1000, 50, 100.0, err="Recursion limit: max retries exceeded in retry loop")
    ]),
    _item("eval-07-hallucinated", "AssistantPlanner", FailurePatternType.HALLUCINATED_TOOL, False, 0, [
        _sp("s1", "fetch_satellite_weather", "tool_call", "error", 1200, 20, 10.0, err="RuntimeError: unknown tool 'fetch_satellite_weather' is not registered")
    ]),
    _item("eval-08-leak-prevention", "SecureProxyAgent", FailurePatternType.SENSITIVE_LEAK_PREVENTED, False, 12, [
        _sp("s1", "prep_req", "agent_step", "success", 800, 300, 25.0,
            in_d="sk-proj-99999999999999999999999999999999 user=alice@example.com Bearer secrettoken12345678901234567890 sk-ant-123456789012345678901234 AKIAIOSFODNN7EXAMPLE email=bob@test.com ssn=001-01-0001",
            out_d="sk-proj-88888888888888888888888888888888 user2=carol@example.com Bearer tokenB123456789012345678901234 sk-ant-987654321098765432109876 AKIA1111111111111111 ssn=002-02-0002")
    ]),
    _item("eval-09-timeout", "WebCrawler", FailurePatternType.TIMEOUT, False, 0, [
        _sp("s1", "http_get", "tool_call", "error", 500, 0, 30000.0, err="TimeoutError: connection timed out after 30000ms")
    ]),
    _item("eval-10-analyst-ok", "DataAnalyst", FailurePatternType.HEALTHY_EXECUTION, False, 0, [
        _sp("s1", "load_data", "tool_call", "success", 1500, 200, 110.0),
        _sp("s2", "compute_corr", "tool_call", "success", 2000, 600, 230.0, parent="s1"),
        _sp("s3", "render_chart", "tool_call", "success", 800, 150, 90.0, parent="s2")
    ]),
    _item("eval-11-retry-cycle-2", "SearchWorker", FailurePatternType.RETRY_LOOP_EXHAUSTION, True, 0, [
        _sp("s1", "search_api", "tool_call", "error", 700, 20, 80.0, err="empty response"),
        _sp("s2", "search_api", "tool_call", "retrying", 700, 20, 80.0, err="empty response"),
        _sp("s3", "search_api", "tool_call", "error", 700, 20, 80.0, err="loop detected: retry count exceeded")
    ]),
    _item("eval-12-rate-limit-2", "BatchProcessor", FailurePatternType.RATE_LIMIT_EXCEEDED, False, 0, [
        _sp("s1", "call_llm_batch", "llm_inference", "error", 4000, 0, 15.0, err="429: Too many tokens per minute requested")
    ])
]


class EvaluationSuite:
    """Benchmark runner for measuring agent trace observability performance."""

    @classmethod
    def run_benchmark(cls) -> EvaluationRunResponse:
        """Run full evaluation suite across benchmark dataset and compute precision/recall/F1."""
        dataset = BENCHMARK_DATASET
        total_samples = len(dataset)
        correct_failure_preds = cycle_tp = cycle_fp = cycle_fn = cycle_tn = 0
        redaction_true_positives = redaction_ground_truth_total = 0
        cost_errors: List[float] = []
        details: List[Dict[str, Any]] = []

        for item in dataset:
            trace_id, spans = item["trace_id"], item["spans"]
            exp_fail, exp_cycles, exp_redacts = item["expected_failure"], item["expected_cycles"], item["expected_redactions"]

            total_redacts = 0
            for s in spans:
                _, m_in = redaction_engine.redact_text(s.get("input_data", ""))
                _, m_out = redaction_engine.redact_text(s.get("output_data", ""))
                total_redacts += len(m_in) + len(m_out)

            if exp_redacts > 0:
                redaction_ground_truth_total += exp_redacts
                redaction_true_positives += min(total_redacts, exp_redacts)

            dag = dag_builder.build_dag(trace_id, spans)
            pred_cycles = dag.has_cycles or dag.retry_loops_detected > 0

            if pred_cycles and exp_cycles:
                cycle_tp += 1
            elif pred_cycles and not exp_cycles:
                cycle_fp += 1
            elif not pred_cycles and exp_cycles:
                cycle_fn += 1
            else:
                cycle_tn += 1

            summary = {
                "duration_seconds": sum(s.get("latency_ms", 0.0) for s in spans) / 1000.0,
                "agent_name": item["agent_name"]
            }
            analysis = failure_analyzer.analyze_trace(summary, spans, dag.has_cycles, dag.retry_loops_detected, total_redacts)
            is_match = analysis.primary_failure == exp_fail
            if is_match:
                correct_failure_preds += 1

            t_prompt = sum(s.get("prompt_tokens", 0) for s in spans)
            t_comp = sum(s.get("completion_tokens", 0) for s in spans)
            calc_cost = cost_engine.calculate_span_cost(t_prompt, t_comp, "qwen3.8-27b")
            exp_cost = ((t_prompt / 1_000_000) * 0.35) + ((t_comp / 1_000_000) * 0.70)
            cost_errors.append(abs(calc_cost - exp_cost))

            details.append({
                "trace_id": trace_id, "agent_name": item["agent_name"],
                "expected_failure": exp_fail.value, "predicted_failure": analysis.primary_failure.value,
                "failure_matched": is_match, "expected_cycles": exp_cycles, "predicted_cycles": pred_cycles,
                "redactions_detected": total_redacts, "anomaly_score": analysis.anomaly_score
            })

        acc = round(correct_failure_preds / total_samples, 4)
        c_p = cycle_tp / (cycle_tp + cycle_fp) if (cycle_tp + cycle_fp) > 0 else 1.0
        c_r = cycle_tp / (cycle_tp + cycle_fn) if (cycle_tp + cycle_fn) > 0 else 1.0
        cycle_f1 = round(2 * c_p * c_r / (c_p + c_r), 4) if (c_p + c_r) > 0 else 1.0
        redact_recall = round(redaction_true_positives / redaction_ground_truth_total, 4) if redaction_ground_truth_total > 0 else 1.0
        cost_mae = round(sum(cost_errors) / len(cost_errors), 6) if cost_errors else 0.0

        def _bm(name: str, score: float, base: float, desc: str):
            passed = score >= base if base > 0.001 else score <= base
            return BenchmarkMetric(metric_name=name, score=score, target_baseline=base, status="PASS" if passed else "FAIL", description=desc)

        metrics = [
            _bm("Failure Pattern Classification Accuracy", acc, 0.90, "Exact match accuracy across failure modes."),
            _bm("Retry Loop & Cycle Detection F1-Score", cycle_f1, 0.95, "F1 identifying tool oscillation loops."),
            _bm("Sensitive Token Redaction Recall", redact_recall, 0.95, "Recall detecting API keys, tokens, emails, SSNs."),
            _bm("Cost Attribution Mean Absolute Error (USD)", cost_mae, 0.0001, "Absolute error vs model rates.")
        ]

        return EvaluationRunResponse(
            run_id=f"eval-{uuid.uuid4().hex[:8]}", dataset_name="agent-trace-benchmark-v1",
            sample_count=total_samples, accuracy=acc, loop_detection_f1=cycle_f1,
            redaction_recall=redact_recall, failure_classification_f1=acc,
            cost_estimation_mae=cost_mae, executed_at=time.time(), metrics=metrics, details=details
        )


def main():
    """CLI entrypoint for standalone evaluation runs."""
    res = EvaluationSuite.run_benchmark()
    print(f"EVAL [{res.dataset_name}]: Samples={res.sample_count} Acc={res.accuracy * 100:.1f}% LoopF1={res.loop_detection_f1 * 100:.1f}% RedactRec={res.redaction_recall * 100:.1f}% MAE=${res.cost_estimation_mae:.6f}")
    for m in res.metrics:
        print(f"[{m.status}] {m.metric_name}: {m.score} (Target: {m.target_baseline})")


if __name__ == "__main__":
    main()
