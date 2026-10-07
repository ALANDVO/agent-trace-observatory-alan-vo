"""Deterministic failure pattern classification and anomaly detection engine."""

import re
from typing import Any, Dict, List, Optional
from app.models.schemas import FailureAnalysis, FailurePatternType
from app.services.cost_engine import cost_engine


class FailureAnalyzer:
    """Classifies agent execution failure modes deterministically based on trace records."""

    @classmethod
    def analyze_trace(
        cls,
        trace_summary: Dict[str, Any],
        spans: List[Dict[str, Any]],
        has_cycles: bool,
        retry_loops_count: int,
        redactions_count: int
    ) -> FailureAnalysis:
        """Evaluate trace spans and metrics to diagnose primary failure patterns."""
        diagnostics: List[str] = []
        token_waste_ratio = cost_engine.calculate_token_waste_ratio(spans)

        # Collect all error messages and statuses
        error_spans = [s for s in spans if s.get("status") in ("error", "retrying") or bool(s.get("error_message"))]
        error_count = len(error_spans)
        all_errors_text = " ".join([str(s.get("error_message", "")) + " " + str(s.get("output_data", "")) for s in error_spans]).lower()

        root_cause_span_id: Optional[str] = None
        root_cause_tool: Optional[str] = None

        if error_spans:
            root_cause_span_id = str(error_spans[0].get("span_id"))
            root_cause_tool = str(error_spans[0].get("span_name"))

        # Determine primary failure type
        primary_failure = FailurePatternType.HEALTHY_EXECUTION
        confidence = 0.95
        remediation = "Execution healthy. All spans completed within normal parameters."

        if redactions_count > 10 and error_count == 0:
            primary_failure = FailurePatternType.SENSITIVE_LEAK_PREVENTED
            confidence = 0.90
            remediation = "Multiple sensitive credentials intercepted before outbound calls. Audit system prompts."
            diagnostics.append(f"Sanitization blocked {redactions_count} sensitive tokens.")
        elif error_count > 0 or has_cycles or retry_loops_count > 0:
            if re.search(r"(?:context length|maximum context|token limit exceeded|prompt is too long|context_window_exceeded)", all_errors_text):
                primary_failure = FailurePatternType.CONTEXT_OVERFLOW
                confidence = 0.98
                remediation = "Compress agent conversation history or truncate tool outputs."
                diagnostics.append("Token context window exceeded.")
            elif re.search(r"(?:429|rate limit|quota exceeded|too many requests|tokens per minute)", all_errors_text):
                primary_failure = FailurePatternType.RATE_LIMIT_EXCEEDED
                confidence = 0.96
                remediation = "Implement exponential backoff or configure dedicated concurrency tier."
                diagnostics.append("Upstream service returned HTTP 429 Rate Limit Exceeded.")
            elif re.search(r"(?:jsondecodeerror|validation error|missing required|invalid parameter|schema validation|bad argument)", all_errors_text):
                primary_failure = FailurePatternType.SCHEMA_VALIDATION_ERROR
                confidence = 0.94
                remediation = "Provide strict JSON schema definitions with validation."
                diagnostics.append(f"Tool '{root_cause_tool or 'unknown'}' received malformed arguments.")
            elif re.search(r"(?:unknown tool|tool not found|not registered|hallucinated function)", all_errors_text):
                primary_failure = FailurePatternType.HALLUCINATED_TOOL
                confidence = 0.95
                remediation = "Constrain tool choice via function-calling prompts."
                diagnostics.append("Agent attempted to invoke an unregistered tool.")
            elif re.search(r"(?:timed out|timeouterror|deadline exceeded|connection timed out)", all_errors_text):
                primary_failure = FailurePatternType.TIMEOUT
                confidence = 0.92
                remediation = "Increase tool timeout threshold or optimize target latency."
                diagnostics.append(f"Tool '{root_cause_tool or 'unknown'}' timed out.")
            elif retry_loops_count >= 2 or has_cycles or re.search(r"(?:max retries|recursion limit|loop detected)", all_errors_text):
                primary_failure = FailurePatternType.RETRY_LOOP_EXHAUSTION
                confidence = 0.93
                remediation = "Introduce circuit breaker heuristics to abort repetitive tool invocations."
                diagnostics.append(f"Detected {retry_loops_count} repetitive tool retry loops.")
            elif re.search(r"(?:exit code|calledprocesserror|command failed|exception|unhandled error)", all_errors_text):
                primary_failure = FailurePatternType.TOOL_EXECUTION_FAILURE
                confidence = 0.90
                remediation = "Inspect tool sandbox environment and permissions."
                diagnostics.append(f"Tool '{root_cause_tool or 'unknown'}' encountered a runtime exception.")
            else:
                primary_failure = FailurePatternType.UNKNOWN_ERROR
                confidence = 0.70
                remediation = "Review raw error logs and span outputs."
                diagnostics.append(f"Unclassified failure in span '{root_cause_span_id or 'unknown'}'.")

        # Anomaly score calculation: 0.0 (normal) to 1.0 (anomalous)
        # Components: error ratio (0.4), token waste ratio (0.3), retry loop presence (0.2), duration outlier (0.1)
        total_spans = max(len(spans), 1)
        error_ratio = min(error_count / total_spans, 1.0)
        retry_component = min(retry_loops_count * 0.35, 1.0)
        duration_component = 0.5 if float(trace_summary.get("duration_seconds", 0.0)) > 60.0 else 0.0

        anomaly_score = round(
            (error_ratio * 0.40) +
            (token_waste_ratio * 0.30) +
            (retry_component * 0.20) +
            (duration_component * 0.10),
            3
        )

        if error_count > 0:
            diagnostics.append(f"{error_count} out of {total_spans} spans resulted in error or retry status.")
        if token_waste_ratio > 0.05:
            diagnostics.append(f"Token waste ratio is {token_waste_ratio * 100:.1f}%, representing unrecovered prompt/completion costs.")

        return FailureAnalysis(
            primary_failure=primary_failure,
            confidence=confidence,
            root_cause_span_id=root_cause_span_id,
            root_cause_tool=root_cause_tool,
            diagnostics=diagnostics,
            anomaly_score=min(anomaly_score, 1.0),
            token_waste_ratio=token_waste_ratio,
            retry_count=retry_loops_count,
            suggested_remediation=remediation
        )


failure_analyzer = FailureAnalyzer()
