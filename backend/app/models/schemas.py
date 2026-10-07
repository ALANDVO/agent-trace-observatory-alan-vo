"""Pydantic schemas for Agent Trace Observatory domain, API payloads, and analytical models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SpanType(str, Enum):
    """Categorization of agent execution spans."""
    TOOL_CALL = "tool_call"
    LLM_INFERENCE = "llm_inference"
    AGENT_STEP = "agent_step"
    MEMORY_RETRIEVAL = "memory_retrieval"
    DECISION = "decision"
    SYSTEM = "system"


class SpanStatus(str, Enum):
    """Execution status of individual span."""
    SUCCESS = "success"
    ERROR = "error"
    RETRYING = "retrying"
    BLOCKED = "blocked"


class TraceStatus(str, Enum):
    """Overall status of multi-step agent trace."""
    COMPLETED = "completed"
    FAILED = "failed"
    RUNNING = "running"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RedactionMatch(BaseModel):
    """Individual detected sensitive entity."""
    category: str
    pattern_name: str
    original_snippet: str
    redacted_snippet: str
    start_pos: int
    end_pos: int


class RedactionReport(BaseModel):
    """Summary of trace redaction execution."""
    total_redactions: int
    categories_detected: Dict[str, int]
    sanitized: bool
    details: List[RedactionMatch] = []


class SpanBase(BaseModel):
    """Core attributes of an execution span."""
    span_id: str
    parent_span_id: Optional[str] = None
    span_name: str
    span_type: SpanType
    model: Optional[str] = None
    input_data: str = ""
    output_data: str = ""
    status: SpanStatus = SpanStatus.SUCCESS
    error_message: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    start_time: float
    end_time: float
    step_index: int = 0


class SpanCreate(SpanBase):
    """Payload for importing an execution span."""
    pass


class SpanResponse(SpanBase):
    """Span model returned to consumers."""
    id: int
    trace_id: str
    redacted_input: str
    redacted_output: str


class TraceImportRequest(BaseModel):
    """Payload to import a structured agent execution trace."""
    trace_id: Optional[str] = None
    agent_name: str
    root_goal: str
    model: str = "qwen3.8-27b"
    status: TraceStatus = TraceStatus.COMPLETED
    spans: List[SpanCreate]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TraceSummaryResponse(BaseModel):
    """Lightweight summary of a trace for lists and tables."""
    id: int
    trace_id: str
    agent_name: str
    status: TraceStatus
    root_goal: str
    model: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    duration_seconds: float
    step_count: int
    tool_call_count: int
    error_count: int
    redactions_count: int
    created_at: float
    updated_at: float


class TraceListResponse(BaseModel):
    """Paginated collection of traces."""
    items: List[TraceSummaryResponse]
    total: int
    limit: int
    offset: int


class DAGNode(BaseModel):
    """A node in the tool-call dependency DAG."""
    id: str
    label: str
    span_type: str
    status: str
    step_index: int
    latency_ms: float
    cost_usd: float
    error_message: Optional[str] = None
    is_root: bool = False
    is_leaf: bool = False


class DAGEdge(BaseModel):
    """A directed dependency or control flow edge."""
    source: str
    target: str
    relationship: str  # parent_child, sequential, retry_loop, data_dependency


class TraceDAGResponse(BaseModel):
    """Full execution graph representation."""
    trace_id: str
    nodes: List[DAGNode]
    edges: List[DAGEdge]
    has_cycles: bool
    cycle_nodes: List[str]
    critical_path: List[str]
    critical_path_latency_ms: float
    parallel_fan_outs: int
    retry_loops_detected: int


class FailurePatternType(str, Enum):
    """Deterministic failure pattern classification."""
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    TOOL_EXECUTION_FAILURE = "TOOL_EXECUTION_FAILURE"
    RETRY_LOOP_EXHAUSTION = "RETRY_LOOP_EXHAUSTION"
    HALLUCINATED_TOOL = "HALLUCINATED_TOOL"
    SENSITIVE_LEAK_PREVENTED = "SENSITIVE_LEAK_PREVENTED"
    TIMEOUT = "TIMEOUT"
    HEALTHY_EXECUTION = "HEALTHY_EXECUTION"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class FailureAnalysis(BaseModel):
    """Comprehensive diagnostic evaluation of trace failure modes."""
    primary_failure: FailurePatternType
    confidence: float
    root_cause_span_id: Optional[str] = None
    root_cause_tool: Optional[str] = None
    diagnostics: List[str]
    anomaly_score: float  # 0.0 (normal) to 1.0 (anomalous)
    token_waste_ratio: float  # Percentage of tokens spent on failed/retrying spans
    retry_count: int
    suggested_remediation: str


class TraceDetailResponse(BaseModel):
    """Detailed trace view with spans, analysis, and redaction stats."""
    summary: TraceSummaryResponse
    spans: List[SpanResponse]
    dag: TraceDAGResponse
    failure_analysis: FailureAnalysis
    redaction_summary: RedactionReport
    metadata: Dict[str, Any]


class AdvisoryLLMRequest(BaseModel):
    """Opt-in request for LLM root cause advisory commentary."""
    custom_prompt: Optional[str] = None


class AdvisoryLLMResponse(BaseModel):
    """Advisory diagnostic generated by configured LLM provider."""
    trace_id: str
    provider: str
    model: str
    is_offline_fallback: bool
    grounded_evidence: List[str]
    explanation_markdown: str
    generated_at: float
    notice: str = "Advisory analysis grounded strictly in parsed trace records. No fabricated responses."


class AggregateStatsResponse(BaseModel):
    """High-level metrics across observatory traces."""
    model_config = {"protected_namespaces": ()}
    total_traces: int
    successful_traces: int
    failed_traces: int
    overall_failure_rate: float
    total_tokens_processed: int
    total_cost_usd: float
    avg_latency_seconds: float
    total_redactions: int
    failure_distribution: Dict[str, int]
    top_failing_tools: List[Dict[str, Any]]
    model_cost_distribution: Dict[str, float]


class BenchmarkMetric(BaseModel):
    """Individual AI/ML benchmark metric item."""
    metric_name: str
    score: float
    target_baseline: float
    status: str
    description: str


class EvaluationRunResponse(BaseModel):
    """Result of running the reproducible evaluation benchmark suite."""
    run_id: str
    dataset_name: str
    sample_count: int
    accuracy: float
    loop_detection_f1: float
    redaction_recall: float
    failure_classification_f1: float
    cost_estimation_mae: float
    executed_at: float
    metrics: List[BenchmarkMetric]
    details: List[Dict[str, Any]]


class AuditLogItem(BaseModel):
    """Individual recorded audit log entry."""
    id: int
    user_id: str
    username: str
    action: str
    resource_type: str
    resource_id: str
    details: str
    ip_address: str
    created_at: float
