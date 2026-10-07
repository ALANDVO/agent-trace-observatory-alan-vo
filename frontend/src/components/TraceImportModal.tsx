/** Trace Import modal supporting JSON upload and pre-loaded failure templates. */

import React, { useState } from 'react';
import { api } from '../api';

interface TraceImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const TEMPLATES = {
  healthy: {
    agent_name: 'CodingAssistant', root_goal: 'Generate REST API endpoint', model: 'qwen3.8-27b',
    spans: [
      { span_id: 'sp-1', span_name: 'read_spec', span_type: 'tool_call', status: 'success', input_data: '{"file": "api.yaml"}', output_data: '{"ok": true}', latency_ms: 60, prompt_tokens: 1100, completion_tokens: 250, start_time: 1.0, end_time: 1.06 },
      { span_id: 'sp-2', parent_span_id: 'sp-1', span_name: 'generate_code', span_type: 'llm_inference', status: 'success', input_data: '{"goal": "route"}', output_data: '{"code": "@app.get()"}', latency_ms: 320, prompt_tokens: 2200, completion_tokens: 750, start_time: 1.06, end_time: 1.38 }
    ]
  },
  retry_loop: {
    agent_name: 'WebCrawlerAgent', root_goal: 'Extract financial statements', model: 'gpt-4o',
    spans: [
      { span_id: 'sp-1', span_name: 'browser_click', span_type: 'tool_call', status: 'error', error_message: 'ElementNotFound', input_data: '{"selector": "#btn"}', output_data: '{}', latency_ms: 1000, prompt_tokens: 1200, completion_tokens: 50, start_time: 1.0, end_time: 2.0 },
      { span_id: 'sp-2', span_name: 'browser_click', span_type: 'tool_call', status: 'retrying', error_message: 'ElementNotFound', input_data: '{"selector": "#btn", "r": 1}', output_data: '{}', latency_ms: 1000, prompt_tokens: 1400, completion_tokens: 50, start_time: 2.0, end_time: 3.0 },
      { span_id: 'sp-3', span_name: 'browser_click', span_type: 'tool_call', status: 'error', error_message: 'Recursion limit: max retries exceeded in retry loop', input_data: '{"selector": "#btn", "r": 2}', output_data: '{}', latency_ms: 1000, prompt_tokens: 1600, completion_tokens: 50, start_time: 3.0, end_time: 4.0 }
    ]
  },
  leak_prevention: {
    agent_name: 'CloudSecurityAuditor', root_goal: 'Audit sensitive infrastructure variables', model: 'claude-3-5-sonnet-20241022',
    spans: [
      { span_id: 'sp-1', span_name: 'dump_env', span_type: 'tool_call', status: 'success', input_data: '{"keys": ["OPENAI_API_KEY"]}', output_data: '{"OPENAI_API_KEY": "sk-proj-123456789012345678901234", "AWS": "AKIAIOSFODNN7EXAMPLE", "contact": "admin@cloud.internal"}', latency_ms: 120, prompt_tokens: 1800, completion_tokens: 300, start_time: 1.0, end_time: 1.12 }
    ]
  }
};

export const TraceImportModal: React.FC<TraceImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [jsonText, setJsonText] = useState(JSON.stringify(TEMPLATES.healthy, null, 2));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.importTrace(JSON.parse(jsonText));
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Import failure');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl max-w-2xl w-full p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-base font-semibold text-slate-100">Import Structured Agent Trace</h3>
            <p className="text-xs text-slate-400 mt-0.5">Paste trajectory JSON. Sensitive credentials and PII will be sanitized.</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400">Sample Templates:</span>
          <button onClick={() => setJsonText(JSON.stringify(TEMPLATES.healthy, null, 2))} className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700">Healthy Code Gen</button>
          <button onClick={() => setJsonText(JSON.stringify(TEMPLATES.retry_loop, null, 2))} className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700">Retry Oscillation Loop</button>
          <button onClick={() => setJsonText(JSON.stringify(TEMPLATES.leak_prevention, null, 2))} className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700">Credential Leak</button>
        </div>

        {error && <div className="p-3 text-xs rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300">{error}</div>}

        <textarea
          rows={10} value={jsonText} onChange={(e) => setJsonText(e.target.value)}
          className="w-full bg-slate-950 font-mono text-xs text-slate-200 border border-slate-800 rounded-lg p-3 focus:outline-none"
        />

        <div className="flex items-center justify-end gap-3 pt-2">
          <button onClick={onClose} className="px-4 py-2 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700">Cancel</button>
          <button onClick={handleImport} disabled={loading} className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50">
            {loading ? 'Importing...' : 'Import Trace'}
          </button>
        </div>
      </div>
    </div>
  );
};
