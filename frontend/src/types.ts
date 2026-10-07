/** Type definitions for Agent Trace Observatory frontend. */

export type SpanType = 'tool_call' | 'llm_inference' | 'agent_step' | 'memory_retrieval' | 'decision' | 'system';
export type SpanStatus = 'success' | 'error' | 'retrying' | 'blocked';
export type TraceStatus = 'completed' | 'failed' | 'running' | 'budget_exhausted';
export type UserRole = 'viewer' | 'analyst' | 'admin';

export interface UserSession {
  user_id: string; username: string; email: string; roles: string[]; csrf_token: string; demo_mode: boolean;
}

export interface Span {
  id: number; span_id: string; parent_span_id: string | null; span_name: string; span_type: SpanType;
  model: string | null; input_data: string; output_data: string; redacted_input: string; redacted_output: string;
  status: SpanStatus; error_message: string; latency_ms: number; prompt_tokens: number; completion_tokens: number;
  cost_usd: number; start_time: number; end_time: number; step_index: number;
}

export interface TraceSummary {
  id: number; trace_id: string; agent_name: string; status: TraceStatus; root_goal: string; model: string;
  total_tokens: number; prompt_tokens: number; completion_tokens: number; total_cost_usd: number;
  duration_seconds: number; step_count: number; tool_call_count: number; error_count: number;
  redactions_count: number; created_at: number; updated_at: number;
}

export interface DAGNode {
  id: string; label: string; span_type: string; status: string; step_index: number;
  latency_ms: number; cost_usd: number; error_message: string | null; is_root: boolean; is_leaf: boolean;
}

export interface DAGEdge {
  source: string; target: string; relationship: string;
}

export interface TraceDAG {
  trace_id: string; nodes: DAGNode[]; edges: DAGEdge[]; has_cycles: boolean; cycle_nodes: string[];
  critical_path: string[]; critical_path_latency_ms: number; parallel_fan_outs: number; retry_loops_detected: number;
}

export interface FailureAnalysis {
  primary_failure: string; confidence: number; root_cause_span_id: string | null; root_cause_tool: string | null;
  diagnostics: string[]; anomaly_score: number; token_waste_ratio: number; retry_count: number; suggested_remediation: string;
}

export interface RedactionMatch {
  category: string; pattern_name: string; original_snippet: string; redacted_snippet: string; start_pos: number; end_pos: number;
}

export interface RedactionReport {
  total_redactions: number; categories_detected: Record<string, number>; sanitized: boolean; details: RedactionMatch[];
}

export interface TraceDetail {
  summary: TraceSummary; spans: Span[]; dag: TraceDAG; failure_analysis: FailureAnalysis;
  redaction_summary: RedactionReport; metadata: Record<string, any>;
}

export interface AdvisoryResponse {
  trace_id: string; provider: string; model: string; is_offline_fallback: boolean;
  grounded_evidence: string[]; explanation_markdown: string; generated_at: number; notice: string;
}

export interface AggregateStats {
  total_traces: number; successful_traces: number; failed_traces: number; overall_failure_rate: number;
  total_tokens_processed: number; total_cost_usd: number; avg_latency_seconds: number; total_redactions: number;
  failure_distribution: Record<string, number>;
  top_failing_tools: Array<{ tool_name: string; failure_count: number; total_calls: number; error_rate: number }>;
  model_cost_distribution: Record<string, number>;
}

export interface BenchmarkMetric {
  metric_name: string; score: number; target_baseline: number; status: string; description: string;
}

export interface EvaluationRun {
  run_id: string; dataset_name: string; sample_count: number; accuracy: number; loop_detection_f1: number;
  redaction_recall: number; failure_classification_f1: number; cost_estimation_mae: number;
  executed_at: number; metrics: BenchmarkMetric[]; details: any[];
}
