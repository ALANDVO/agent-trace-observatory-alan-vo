/** AI/ML evaluation benchmark dashboard with reproducible execution and dataset viewer. */

import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { BenchmarkMetric, EvaluationRun } from '../types';

interface EvaluationViewProps {
  onBack: () => void;
  canRunEvaluation: boolean;
}

export const EvaluationView: React.FC<EvaluationViewProps> = ({ onBack, canRunEvaluation }) => {
  const [loading, setLoading] = useState(false);
  const [runResult, setRunResult] = useState<EvaluationRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [datasetInfo, setDatasetInfo] = useState<{ total_samples: number; samples: any[] } | null>(null);

  useEffect(() => {
    loadDataset();
  }, []);

  const loadDataset = async () => {
    try {
      const data = await api.getBenchmarkDataset();
      setDatasetInfo(data);
    } catch {
      // ignore
    }
  };

  const handleRunBenchmark = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.runBenchmark();
      setRunResult(res);
    } catch (err: any) {
      setError(err.message || 'Benchmark execution failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg">
        <div>
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="px-3 py-1 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
            >
              ← Back to Traces
            </button>
            <h2 className="text-xl font-bold text-slate-100">AI/ML Agent Benchmark Evaluation</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Reproducible offline evaluation baseline measuring multi-step failure pattern classification, loop detection, and redaction recall.
          </p>
        </div>

        <div>
          <button
            onClick={handleRunBenchmark}
            disabled={loading || !canRunEvaluation}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 transition shadow-md"
          >
            {loading ? 'Running Benchmark...' : 'Execute Reproducible Benchmark'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 text-xs rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300">
          {error}
        </div>
      )}

      {runResult && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {runResult.metrics.map((m: BenchmarkMetric, idx: number) => (
              <div key={idx} className="bg-slate-900 border border-slate-800 p-4 rounded-xl shadow">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-slate-400 font-medium truncate" title={m.metric_name}>{m.metric_name}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase border ${m.status === 'PASS' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'}`}>{m.status}</span>
                </div>
                <div className="text-2xl font-bold text-slate-100 font-mono">
                  {typeof m.score === 'number' && m.score <= 1.0 && m.score >= 0.0 && m.score !== 0 ? `${(m.score * 100).toFixed(1)}%` : m.score.toFixed(4)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">Target: {m.target_baseline <= 1.0 ? `${(m.target_baseline * 100).toFixed(0)}%` : m.target_baseline}</div>
                <p className="text-[10px] text-slate-400 mt-2 line-clamp-2">{m.description}</p>
              </div>
            ))}
          </div>

          <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-3">
            <h3 className="text-sm font-semibold text-slate-100">Evaluated Trajectory Sample Results</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300 font-mono text-[11px]">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="py-2 px-3">Trace ID</th>
                    <th className="py-2 px-3">Agent</th>
                    <th className="py-2 px-3">Expected</th>
                    <th className="py-2 px-3">Predicted</th>
                    <th className="py-2 px-3">Match</th>
                    <th className="py-2 px-3">Cycles</th>
                    <th className="py-2 px-3">Redacted</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {runResult.details.map((d: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="py-2 px-3 text-indigo-300">{d.trace_id}</td>
                      <td className="py-2 px-3 text-slate-400 font-sans">{d.agent_name}</td>
                      <td className="py-2 px-3 text-slate-300">{d.expected_failure}</td>
                      <td className="py-2 px-3 text-slate-200 font-semibold">{d.predicted_failure}</td>
                      <td className="py-2 px-3">{d.failure_matched ? <span className="text-emerald-400 font-bold">✓ Match</span> : <span className="text-rose-400 font-bold">✗ Diff</span>}</td>
                      <td className="py-2 px-3 text-slate-400">{d.predicted_cycles ? 'Detected' : 'None'}</td>
                      <td className="py-2 px-3 text-amber-400">{d.redactions_detected}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {datasetInfo && !runResult && (
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-3">
          <h3 className="text-sm font-semibold text-slate-100">Curated Benchmark Trajectories ({datasetInfo.total_samples} labeled cases)</h3>
          <p className="text-xs text-slate-400">Dataset covers context overflow, rate limits, schema errors, tool exceptions, retry loops, and sensitive leakage.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 pt-2">
            {datasetInfo.samples.map((s: any, idx: number) => (
              <div key={idx} className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs space-y-1">
                <div className="font-mono text-indigo-300 font-semibold truncate">{s.trace_id}</div>
                <div className="text-slate-400 text-[11px]">Agent: {s.agent_name}</div>
                <div className="text-slate-400 text-[11px]">Pattern: <span className="text-slate-200 font-mono">{s.expected_failure}</span></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
