import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from '../App';
import { DAGVisualizer } from '../components/DAGVisualizer';
import { TraceImportModal } from '../components/TraceImportModal';
import { TraceDAG } from '../types';

// Mock fetch for API calls
beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/api/auth/me')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              user_id: 'test-user',
              username: 'operator',
              email: 'operator@example.com',
              roles: ['admin'],
              csrf_token: 'test-csrf-token',
              demo_mode: true
            })
        });
      }
      if (url.includes('/api/analytics/overview')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total_traces: 12,
              successful_traces: 8,
              failed_traces: 4,
              overall_failure_rate: 0.3333,
              total_tokens_processed: 45000,
              total_cost_usd: 0.125,
              avg_latency_seconds: 4.5,
              total_redactions: 8,
              failure_distribution: { CONTEXT_OVERFLOW: 2, RETRY_LOOP_EXHAUSTION: 2 },
              top_failing_tools: [],
              model_cost_distribution: {}
            })
        });
      }
      if (url.includes('/api/traces')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: 1,
                  trace_id: 'trace-test-101',
                  agent_name: 'TestCodeGenAgent',
                  status: 'completed',
                  root_goal: 'Write REST endpoint',
                  model: 'qwen3.8-27b',
                  total_tokens: 1500,
                  prompt_tokens: 1000,
                  completion_tokens: 500,
                  total_cost_usd: 0.001,
                  duration_seconds: 2.5,
                  step_count: 2,
                  tool_call_count: 1,
                  error_count: 0,
                  redactions_count: 1,
                  created_at: 1000,
                  updated_at: 1000
                }
              ],
              total: 1,
              limit: 15,
              offset: 0
            })
        });
      }
      if (url.includes('/api/evaluation/dataset')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              dataset_name: 'agent-trace-benchmark-v1',
              total_samples: 12,
              samples: [
                {
                  trace_id: 'eval-01',
                  agent_name: 'CodeGen',
                  expected_failure: 'HEALTHY_EXECUTION',
                  expected_cycles: false,
                  expected_redactions: 0
                }
              ]
            })
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      });
    })
  );
});

describe('Agent Trace Observatory Frontend', () => {
  it('renders application header and author branding', async () => {
    render(<App />);
    expect(screen.getByText('Agent Trace Observatory')).toBeInTheDocument();
    expect(screen.getByText(/Alan Vo \| AI & Machine Learning/i)).toBeInTheDocument();
  });

  it('navigates to AI/ML evaluation view and shows benchmark action', async () => {
    render(<App />);
    const evalButton = screen.getByText('AI/ML Evaluation');
    fireEvent.click(evalButton);

    await waitFor(() => {
      expect(screen.getByText(/AI\/ML Agent Benchmark Evaluation/i)).toBeInTheDocument();
      expect(screen.getByText('Execute Reproducible Benchmark')).toBeInTheDocument();
    });
  });

  it('renders DAG Visualizer with node statuses and critical path metrics', () => {
    const mockDAG: TraceDAG = {
      trace_id: 'dag-test-01',
      nodes: [
        {
          id: 'n1',
          label: 'search_tool',
          span_type: 'tool_call',
          status: 'error',
          step_index: 0,
          latency_ms: 250,
          cost_usd: 0.002,
          error_message: 'Timed out',
          is_root: true,
          is_leaf: false
        }
      ],
      edges: [],
      has_cycles: true,
      cycle_nodes: ['n1'],
      critical_path: ['n1'],
      critical_path_latency_ms: 250,
      parallel_fan_outs: 0,
      retry_loops_detected: 1
    };

    render(<DAGVisualizer dag={mockDAG} selectedNodeId={null} onSelectNode={() => {}} />);
    expect(screen.getByText('Tool-Call Execution DAG')).toBeInTheDocument();
    expect(screen.getByText(/Cycle \/ Retry Loop Detected/i)).toBeInTheDocument();
    expect(screen.getByText('search_tool')).toBeInTheDocument();
  });

  it('renders TraceImportModal and allows selecting sample templates', () => {
    const handleClose = vi.fn();
    render(<TraceImportModal isOpen={true} onClose={handleClose} onSuccess={() => {}} />);

    expect(screen.getByText('Import Structured Agent Trace')).toBeInTheDocument();
    expect(screen.getByText('Retry Oscillation Loop')).toBeInTheDocument();
    expect(screen.getByText('Credential Leak')).toBeInTheDocument();

    const retryTemplateBtn = screen.getByText('Retry Oscillation Loop');
    fireEvent.click(retryTemplateBtn);

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea.value).toContain('WebCrawlerAgent');
  });
});
