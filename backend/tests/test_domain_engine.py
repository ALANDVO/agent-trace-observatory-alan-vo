"""Tests for domain services: redaction, DAG construction, cost accounting, failure diagnosis, and evaluation."""

import pytest
from app.models.schemas import FailurePatternType
from app.services.cost_engine import cost_engine
from app.services.dag_builder import dag_builder
from app.services.evaluator import EvaluationSuite
from app.services.failure_analyzer import failure_analyzer
from app.services.redaction import luhn_checksum_valid, redaction_engine


def test_redaction_api_keys():
    """Verify detection and masking of API keys from OpenAI, Anthropic, AWS, GitHub."""
    # Generated dummy value for detector coverage; never a usable credential.
    synthetic_github_pat = "ghp_" + "0" * 36
    text = (
        "Here is my OpenAI key sk-proj-123456789012345678901234 and Anthropic sk-ant-abcdefghijklmnop123456 "
        f"and AWS AKIAIOSFODNN7EXAMPLE and GitHub {synthetic_github_pat}"
    )
    sanitized, matches = redaction_engine.redact_text(text)
    assert "[REDACTED:OPENAI_KEY]" in sanitized
    assert "[REDACTED:ANTHROPIC_KEY]" in sanitized
    assert "[REDACTED:AWS_ACCESS_KEY]" in sanitized
    assert "[REDACTED:GITHUB_PAT]" in sanitized
    assert len(matches) == 4


def test_redaction_pii_and_luhn():
    """Verify masking of emails, SSN, IPv4, and credit cards with Luhn checksum validation."""
    valid_card = "4532015112830366"  # valid visa test number
    assert luhn_checksum_valid(valid_card)
    assert not luhn_checksum_valid("4532015112830367")

    text = f"Contact operator@example.com with SSN 123-45-6789 at 198.51.100.14 using card {valid_card}"
    sanitized, matches = redaction_engine.redact_text(text)
    assert "[REDACTED:EMAIL]" in sanitized
    assert "[REDACTED:US_SSN]" in sanitized
    assert "[REDACTED:IPV4_ADDRESS]" in sanitized
    assert "[REDACTED:CREDIT_CARD]" in sanitized
    assert len(matches) == 4


def test_dag_builder_structure_and_cycles():
    """Verify directed acyclic graph construction, parent-child links, and cycle detection."""
    spans = [
        {"span_id": "root", "span_name": "agent_start", "span_type": "agent_step", "status": "success", "latency_ms": 10.0, "step_index": 0},
        {"span_id": "t1", "parent_span_id": "root", "span_name": "web_search", "span_type": "tool_call", "status": "error", "error_message": "failed", "latency_ms": 50.0, "step_index": 1},
        {"span_id": "t2", "parent_span_id": "t1", "span_name": "web_search", "span_type": "tool_call", "status": "error", "error_message": "failed", "latency_ms": 50.0, "step_index": 2}
    ]
    dag = dag_builder.build_dag("trace-cycle-test", spans)
    assert len(dag.nodes) == 3
    assert len(dag.edges) >= 2
    assert dag.has_cycles is True or dag.retry_loops_detected >= 1
    assert "t1" in dag.cycle_nodes or "t2" in dag.cycle_nodes


def test_dag_builder_critical_path():
    """Verify critical path latency calculation across sequence of spans."""
    spans = [
        {"span_id": "s1", "span_name": "step1", "span_type": "agent_step", "status": "success", "latency_ms": 100.0, "step_index": 0},
        {"span_id": "s2", "parent_span_id": "s1", "span_name": "step2", "span_type": "tool_call", "status": "success", "latency_ms": 250.0, "step_index": 1},
        {"span_id": "s3", "parent_span_id": "s2", "span_name": "step3", "span_type": "tool_call", "status": "success", "latency_ms": 150.0, "step_index": 2}
    ]
    dag = dag_builder.build_dag("trace-crit-test", spans)
    assert dag.critical_path_latency_ms >= 500.0
    assert dag.critical_path == ["s1", "s2", "s3"]


def test_cost_engine_pricing():
    """Verify token cost calculations and token waste proportion."""
    cost_gpt4o = cost_engine.calculate_span_cost(1000, 1000, "gpt-4o")
    # 1000 prompt @ $2.50/M = 0.0025, 1000 comp @ $10.00/M = 0.010 -> total 0.0125
    assert cost_gpt4o == 0.0125

    cost_qwen = cost_engine.calculate_span_cost(1000, 1000, "qwen3.8-27b")
    # 1000 prompt @ $0.35/M = 0.00035, 1000 comp @ $0.70/M = 0.00070 -> total 0.00105
    assert cost_qwen == 0.00105

    spans = [
        {"prompt_tokens": 1000, "completion_tokens": 500, "status": "success"},
        {"prompt_tokens": 1000, "completion_tokens": 500, "status": "error", "error_message": "failed"}
    ]
    waste_ratio = cost_engine.calculate_token_waste_ratio(spans)
    assert waste_ratio == 0.5


def test_failure_analyzer_patterns():
    """Verify deterministic failure classification for context overflow, rate limit, schema error, and healthy runs."""
    # Context overflow
    res_ctx = failure_analyzer.analyze_trace(
        {"duration_seconds": 5.0, "agent_name": "Test"},
        [{"span_id": "s1", "span_name": "llm", "status": "error", "error_message": "maximum context length exceeded"}],
        False, 0, 0
    )
    assert res_ctx.primary_failure == FailurePatternType.CONTEXT_OVERFLOW
    assert res_ctx.confidence > 0.9

    # Rate limit
    res_rl = failure_analyzer.analyze_trace(
        {"duration_seconds": 5.0, "agent_name": "Test"},
        [{"span_id": "s1", "span_name": "api", "status": "error", "error_message": "HTTP 429 Too Many Requests: rate limit exceeded"}],
        False, 0, 0
    )
    assert res_rl.primary_failure == FailurePatternType.RATE_LIMIT_EXCEEDED

    # Schema error
    res_schema = failure_analyzer.analyze_trace(
        {"duration_seconds": 5.0, "agent_name": "Test"},
        [{"span_id": "s1", "span_name": "tool_sql", "status": "error", "error_message": "ValidationError: missing required field 'query'"}],
        False, 0, 0
    )
    assert res_schema.primary_failure == FailurePatternType.SCHEMA_VALIDATION_ERROR

    # Healthy
    res_ok = failure_analyzer.analyze_trace(
        {"duration_seconds": 5.0, "agent_name": "Test"},
        [{"span_id": "s1", "span_name": "tool_sql", "status": "success", "error_message": ""}],
        False, 0, 0
    )
    assert res_ok.primary_failure == FailurePatternType.HEALTHY_EXECUTION
    assert res_ok.anomaly_score == 0.0


def test_benchmark_evaluator_metrics():
    """Verify reproducible benchmark suite runs and computes passing metrics."""
    result = EvaluationSuite.run_benchmark()
    assert result.sample_count >= 10
    assert result.accuracy >= 0.90
    assert result.loop_detection_f1 >= 0.95
    assert result.redaction_recall >= 0.95
    assert result.cost_estimation_mae <= 0.0001
    assert len(result.metrics) == 4
    for m in result.metrics:
        assert m.status == "PASS"
