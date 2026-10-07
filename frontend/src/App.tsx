/** Main Application Component for Agent Trace Observatory. */

import React, { useEffect, useState } from 'react';
import { api } from './api';
import { EvaluationView } from './components/EvaluationView';
import { TraceDetail } from './components/TraceDetail';
import { TraceImportModal } from './components/TraceImportModal';
import { AggregateStats, TraceDetail as ITraceDetail, TraceSummary, UserRole, UserSession } from './types';

const B_CLS = "bg-slate-900 border border-slate-800 rounded-xl shadow";
const BTN_SM = "px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition";

export const App: React.FC = () => {
  const [session, setSession] = useState<UserSession | null>(null);
  const [overview, setOverview] = useState<AggregateStats | null>(null);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [totalTraces, setTotalTraces] = useState(0);
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [hasErrorsFilter, setHasErrorsFilter] = useState<boolean | undefined>(undefined);

  const [traceDetail, setTraceDetail] = useState<ITraceDetail | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'detail' | 'evaluation'>('dashboard');
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { initApp(); }, []);
  useEffect(() => { if (activeTab === 'dashboard') loadTraces(); }, [page, statusFilter, modelFilter, hasErrorsFilter, activeTab]);

  const initApp = async () => {
    setLoading(true);
    try {
      setSession(await api.getMe());
      setOverview(await api.getOverview());
      await loadTraces();
    } catch (err: any) {
      setError(err.message || 'Initialization failed');
    } finally {
      setLoading(false);
    }
  };

  const loadTraces = async () => {
    try {
      const res = await api.getTraces({
        search: search || undefined, status: statusFilter || undefined,
        model: modelFilter || undefined, has_errors: hasErrorsFilter,
        limit: pageSize, offset: page * pageSize
      });
      setTraces(res.items);
      setTotalTraces(res.total);
    } catch (err: any) {
      setError(err.message || 'Failed to load traces');
    }
  };

  const handleInspectTrace = async (traceId: string) => {
    setLoading(true); setError(null);
    try { setTraceDetail(await api.getTraceDetail(traceId)); setActiveTab('detail'); }
    catch (err: any) { setError(err.message || 'Trace detail error'); }
    finally { setLoading(false); }
  };

  const handleDeleteTrace = async (traceId: string) => {
    if (!window.confirm(`Delete trace '${traceId}'?`)) return;
    try { await api.deleteTrace(traceId); setActiveTab('dashboard'); setTraceDetail(null); await initApp(); }
    catch (err: any) { alert(`Deletion failed: ${err.message}`); }
  };

  const handleSwitchRole = async (role: UserRole) => {
    try { setSession(await api.switchRole(role)); } catch (err: any) { alert(err.message); }
  };

  const userRoles = session?.roles || [];
  const isAdmin = userRoles.includes('admin');
  const isAnalyst = isAdmin || userRoles.includes('analyst');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <header className="border-b border-slate-800 bg-slate-900/90 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-mono font-bold text-white">Ω</div>
            <div>
              <h1 className="text-base font-bold text-slate-100">Agent Trace Observatory</h1>
              <div className="text-[11px] text-slate-400">Alan Vo | AI & Machine Learning</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={() => setActiveTab('dashboard')} className={`px-3 py-1.5 text-xs rounded-lg transition ${activeTab === 'dashboard' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>Dashboard</button>
            <button onClick={() => setActiveTab('evaluation')} className={`px-3 py-1.5 text-xs rounded-lg transition ${activeTab === 'evaluation' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>AI/ML Evaluation</button>
            {session?.demo_mode && (
              <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 rounded-lg p-1 text-xs">
                {(['viewer', 'analyst', 'admin'] as UserRole[]).map((r) => (
                  <button key={r} onClick={() => handleSwitchRole(r)} className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize ${userRoles.includes(r) ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-400'}`}>{r}</button>
                ))}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 space-y-5">
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs flex justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {activeTab === 'detail' && traceDetail ? (
          <TraceDetail trace={traceDetail} onBack={() => setActiveTab('dashboard')} onDelete={handleDeleteTrace} isAdmin={isAdmin} />
        ) : activeTab === 'evaluation' ? (
          <EvaluationView onBack={() => setActiveTab('dashboard')} canRunEvaluation={isAnalyst} />
        ) : (
          <div className="space-y-5">
            {overview && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {[
                  { l: 'Total Traces', v: overview.total_traces, c: 'text-slate-100' },
                  { l: 'Failure Rate', v: `${(overview.overall_failure_rate * 100).toFixed(1)}%`, c: 'text-rose-400' },
                  { l: 'Total Tokens', v: overview.total_tokens_processed.toLocaleString(), c: 'text-slate-100' },
                  { l: 'Cost (USD)', v: `$${overview.total_cost_usd.toFixed(4)}`, c: 'text-emerald-400' },
                  { l: 'Avg Duration', v: `${overview.avg_latency_seconds.toFixed(2)}s`, c: 'text-slate-100' },
                  { l: 'Redactions', v: overview.total_redactions, c: 'text-amber-400' }
                ].map((m, idx) => (
                  <div key={idx} className={`${B_CLS} p-3.5`}>
                    <div className="text-[11px] text-slate-400">{m.l}</div>
                    <div className={`text-lg font-bold font-mono mt-0.5 ${m.c}`}>{m.v}</div>
                  </div>
                ))}
              </div>
            )}

            <div className={`${B_CLS} p-3.5 flex flex-wrap items-center justify-between gap-3`}>
              <form onSubmit={(e) => { e.preventDefault(); setPage(0); loadTraces(); }} className="flex flex-wrap items-center gap-2 flex-1">
                <input type="text" placeholder="Search traces..." value={search} onChange={(e) => setSearch(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 w-44" />
                <input type="text" placeholder="Filter model..." value={modelFilter} onChange={(e) => setModelFilter(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 w-28" />
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-300">
                  <option value="">All Statuses</option><option value="completed">Completed</option><option value="failed">Failed</option>
                </select>
                <select value={hasErrorsFilter === undefined ? '' : String(hasErrorsFilter)} onChange={(e) => setHasErrorsFilter(e.target.value === '' ? undefined : e.target.value === 'true')} className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-300">
                  <option value="">All Health</option><option value="true">Has Errors</option><option value="false">Healthy</option>
                </select>
                <button type="submit" className={BTN_SM}>Filter</button>
              </form>

              <div className="flex items-center gap-2">
                <button onClick={() => window.open('/api/export/traces?format=csv', '_blank')} className={BTN_SM}>Export CSV</button>
                <button onClick={() => window.open('/api/export/traces?format=json', '_blank')} className={BTN_SM}>Export JSON</button>
                {isAnalyst && <button onClick={() => setIsImportOpen(true)} className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500">+ Import Trace</button>}
              </div>
            </div>

            <div className={`${B_CLS} overflow-hidden`}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] border-b border-slate-800 uppercase">
                    <tr>
                      {['Trace ID', 'Agent', 'Goal', 'Status', 'Tokens', 'Cost', 'Duration', 'Redactions'].map((h) => <th key={h} className="py-2 px-3">{h}</th>)}
                      <th className="py-2 px-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {traces.length === 0 ? (
                      <tr><td colSpan={9} className="py-8 text-center text-slate-500 font-sans">{loading ? 'Loading...' : 'No traces found.'}</td></tr>
                    ) : (
                      traces.map((t) => (
                        <tr key={t.trace_id} className="hover:bg-slate-800/40 cursor-pointer" onClick={() => handleInspectTrace(t.trace_id)}>
                          <td className="py-2 px-3 text-indigo-300 font-semibold">{t.trace_id}</td>
                          <td className="py-2 px-3 font-sans text-slate-200">{t.agent_name}</td>
                          <td className="py-2 px-3 font-sans max-w-xs truncate text-slate-400">{t.root_goal}</td>
                          <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${t.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>{t.status}</span></td>
                          <td className="py-2 px-3 text-slate-400">{t.total_tokens.toLocaleString()}</td>
                          <td className="py-2 px-3 text-emerald-400">${t.total_cost_usd.toFixed(5)}</td>
                          <td className="py-2 px-3 text-slate-400">{t.duration_seconds.toFixed(2)}s</td>
                          <td className="py-2 px-3 text-amber-400">{t.redactions_count}</td>
                          <td className="py-2 px-3 text-right"><button onClick={(e) => { e.stopPropagation(); handleInspectTrace(t.trace_id); }} className="px-2 py-1 rounded bg-slate-800 text-[11px] hover:bg-indigo-600">Inspect</button></td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {totalTraces > pageSize && (
                <div className="p-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                  <span>Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, totalTraces)} of {totalTraces}</span>
                  <div className="flex gap-2">
                    <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-1 rounded bg-slate-800 disabled:opacity-40">Prev</button>
                    <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * pageSize >= totalTraces} className="px-2 py-1 rounded bg-slate-800 disabled:opacity-40">Next</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-500">
        Agent Trace Observatory &copy; 2026 Alan Vo &lt;<a href="mailto:alanvo@gmail.com" className="text-indigo-400">alanvo@gmail.com</a>&gt;
      </footer>

      <TraceImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onSuccess={() => { loadTraces(); api.getOverview().then(setOverview); }} />
    </div>
  );
};
