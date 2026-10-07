/** Detailed Trace view with DAG, failure diagnosis, advisory assistant, and span inspector. */

import React, { useState } from 'react';
import { api } from '../api';
import { AdvisoryResponse, Span, TraceDetail as ITraceDetail } from '../types';
import { DAGVisualizer } from './DAGVisualizer';

interface TraceDetailProps {
  trace: ITraceDetail;
  onBack: () => void;
  onDelete?: (traceId: string) => void;
  isAdmin: boolean;
}

const B_CLS = "bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-lg space-y-4";

export const TraceDetail: React.FC<TraceDetailProps> = ({ trace, onBack, onDelete, isAdmin }) => {
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [showRedacted, setShowRedacted] = useState(true);
  const [advisoryLoading, setAdvisoryLoading] = useState(false);
  const [advisory, setAdvisory] = useState<AdvisoryResponse | null>(null);
  const [customPrompt, setCustomPrompt] = useState('');
  const [advisoryError, setAdvisoryError] = useState<string | null>(null);

  const { summary, failure_analysis, redaction_summary } = trace;
  const selectedSpan: Span | undefined = trace.spans.find((s) => s.span_id === selectedSpanId);

  const handleRequestAdvisory = async () => {
    setAdvisoryLoading(true);
    setAdvisoryError(null);
    try {
      setAdvisory(await api.getAdvisory(summary.trace_id, customPrompt || undefined));
    } catch (err: any) {
      setAdvisoryError(err.message || 'Advisory request failed');
    } finally {
      setAdvisoryLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-xl shadow">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="px-2.5 py-1 text-xs rounded bg-slate-800 text-slate-300">← Back</button>
            <h2 className="text-lg font-bold font-mono text-slate-100">{summary.trace_id}</h2>
            <span className={`text-xs px-2 py-0.5 rounded-full font-semibold uppercase ${summary.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>{summary.status}</span>
          </div>
          <p className="text-xs text-slate-300">{summary.root_goal}</p>
          <p className="text-[11px] text-slate-400">Agent: <span className="text-indigo-300">{summary.agent_name}</span> | Model: <span className="font-mono">{summary.model}</span></p>
        </div>
        {isAdmin && onDelete && (
          <button onClick={() => onDelete(summary.trace_id)} className="px-3 py-1.5 text-xs rounded-lg bg-rose-950/60 text-rose-400 border border-rose-800">Delete Trace</button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { l: 'Total Cost', v: `$${summary.total_cost_usd.toFixed(5)}`, c: 'text-emerald-400' },
          { l: 'Total Tokens', v: summary.total_tokens.toLocaleString(), c: 'text-slate-100' },
          { l: 'Duration', v: `${summary.duration_seconds.toFixed(2)}s`, c: 'text-slate-100' },
          { l: 'Tool Calls', v: summary.tool_call_count, c: 'text-indigo-400' },
          { l: 'Error Spans', v: summary.error_count, c: 'text-rose-400' },
          { l: 'Redacted', v: summary.redactions_count, c: 'text-amber-400' }
        ].map((s, idx) => (
          <div key={idx} className="bg-slate-900 border border-slate-800 p-3 rounded-lg">
            <div className="text-[11px] text-slate-400">{s.l}</div>
            <div className={`text-base font-semibold font-mono ${s.c}`}>{s.v}</div>
          </div>
        ))}
      </div>

      <div className={B_CLS}>
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Deterministic Failure Diagnosis</h3>
            <p className="text-xs text-slate-400">Rule-based pattern classification grounded in trace spans.</p>
          </div>
          <span className="font-mono text-xs px-2 py-0.5 rounded font-bold bg-slate-800 text-amber-300">Anomaly: {failure_analysis.anomaly_score.toFixed(3)}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="space-y-1.5 text-slate-300">
            <div>Pattern: <strong className="font-mono text-indigo-300">{failure_analysis.primary_failure}</strong> ({(failure_analysis.confidence * 100).toFixed(0)}%)</div>
            {failure_analysis.root_cause_tool && <div>Root Cause: <strong className="font-mono text-rose-300">{failure_analysis.root_cause_tool}</strong></div>}
            <div>Waste Ratio: <strong className="font-mono text-amber-300">{(failure_analysis.token_waste_ratio * 100).toFixed(1)}%</strong></div>
            <div>Retry Loops: <strong className="font-mono text-slate-200">{failure_analysis.retry_count}</strong></div>
          </div>
          <div className="space-y-1">
            <div className="text-slate-400 font-semibold">Remediation:</div>
            <p className="bg-slate-950 p-2.5 rounded border border-slate-800 leading-relaxed text-slate-300">{failure_analysis.suggested_remediation}</p>
          </div>
        </div>
        {failure_analysis.diagnostics.length > 0 && (
          <div className="pt-2 border-t border-slate-800 text-xs">
            <ul className="text-slate-300 space-y-0.5 list-disc pl-5">
              {failure_analysis.diagnostics.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          </div>
        )}
      </div>

      <DAGVisualizer dag={trace.dag} selectedNodeId={selectedSpanId} onSelectNode={setSelectedSpanId} />

      <div className={B_CLS}>
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Advisory Root-Cause Assistant</h3>
            <p className="text-xs text-slate-400">Opt-in grounded analysis via configured provider or offline core.</p>
          </div>
          <button onClick={handleRequestAdvisory} disabled={advisoryLoading} className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">
            {advisoryLoading ? 'Analyzing...' : 'Generate Advisory'}
          </button>
        </div>
        <input
          type="text" placeholder="Optional inquiry (e.g. 'Why did tool fail?')"
          value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
          className="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200"
        />
        {advisoryError && <div className="p-2.5 text-xs rounded bg-rose-950/60 border border-rose-800 text-rose-300">{advisoryError}</div>}
        {advisory && (
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs space-y-2">
            <div className="flex justify-between text-slate-500 border-b border-slate-800 pb-1">
              <span>{advisory.provider} ({advisory.model})</span>
              <span className="text-amber-400 italic">{advisory.notice}</span>
            </div>
            <div className="whitespace-pre-wrap leading-relaxed text-slate-200">{advisory.explanation_markdown}</div>
          </div>
        )}
      </div>

      <div className={B_CLS}>
        <div className="flex justify-between items-center pb-2 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-slate-100">Execution Spans</h3>
          <button onClick={() => setShowRedacted(!showRedacted)} className="px-3 py-1 rounded text-xs bg-slate-800 text-slate-300">
            {showRedacted ? '🛡️ Redacted' : '⚠️ Raw Data'}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300 font-mono">
            <thead className="bg-slate-950 text-slate-500 text-[11px] border-b border-slate-800 uppercase">
              <tr>
                <th className="py-2 px-3">#</th><th className="py-2 px-3">Name</th><th className="py-2 px-3">Type</th><th className="py-2 px-3">Status</th><th className="py-2 px-3">Cost</th><th className="py-2 px-3">Latency</th><th className="py-2 px-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {trace.spans.map((s, idx) => (
                <tr key={s.span_id} className={`hover:bg-slate-800/40 cursor-pointer ${selectedSpanId === s.span_id ? 'bg-slate-800' : ''}`} onClick={() => setSelectedSpanId(s.span_id)}>
                  <td className="py-2 px-3 text-slate-500">{idx + 1}</td>
                  <td className="py-2 px-3 text-indigo-300 font-semibold">{s.span_name}</td>
                  <td className="py-2 px-3 text-slate-400 capitalize">{s.span_type}</td>
                  <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-[10px] ${s.status === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>{s.status}</span></td>
                  <td className="py-2 px-3 text-emerald-400">${s.cost_usd.toFixed(5)}</td>
                  <td className="py-2 px-3 text-slate-400">{s.latency_ms.toFixed(1)}ms</td>
                  <td className="py-2 px-3"><button onClick={() => setSelectedSpanId(s.span_id)} className="text-indigo-400 hover:underline">View</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selectedSpan && (
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2 text-xs font-mono">
            <div className="flex justify-between text-slate-300 font-semibold">
              <span>Span: {selectedSpan.span_name}</span>
              <button onClick={() => setSelectedSpanId(null)}>Close</button>
            </div>
            {selectedSpan.error_message && <div className="text-rose-300">Error: {selectedSpan.error_message}</div>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
              <div>
                <div className="text-slate-500 mb-0.5">Input:</div>
                <pre className="bg-slate-900 p-2 rounded border border-slate-800 overflow-x-auto max-h-36 whitespace-pre-wrap">{showRedacted ? selectedSpan.redacted_input : selectedSpan.input_data}</pre>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">Output:</div>
                <pre className="bg-slate-900 p-2 rounded border border-slate-800 overflow-x-auto max-h-36 whitespace-pre-wrap">{showRedacted ? selectedSpan.redacted_output : selectedSpan.output_data}</pre>
              </div>
            </div>
          </div>
        )}
      </div>

      {redaction_summary.total_redactions > 0 && (
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-xs space-y-2">
          <div className="font-semibold text-slate-200">Sanitization: {redaction_summary.total_redactions} Secrets Intercepted</div>
          <div className="flex gap-2">
            {Object.entries(redaction_summary.categories_detected).map(([cat, count]) => (
              <span key={cat} className="px-2 py-0.5 bg-slate-800 rounded text-slate-300 font-mono">{cat}: {count}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
