/** Agent Trace Observatory main component. */
import React, { useEffect, useState } from 'react';
import { api } from './api';
import { EvaluationView } from './components/EvaluationView';
import { TraceDetail } from './components/TraceDetail';
import { TraceImportModal } from './components/TraceImportModal';
import { RedactionRulesManager } from './components/RedactionRulesManager';
import { AggregateStats, TraceDetail as ITraceDetail, TraceSummary, UserRole, UserSession } from './types';

const B = "bg-slate-900 border border-slate-800 rounded-xl shadow";
const BS = "px-3 py-1.5 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700";

export const App: React.FC = () => {
  const [session, setSession] = useState<UserSession|null>(null);
  const [overview, setOverview] = useState<AggregateStats|null>(null);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const ps = 15;
  const [search, setSearch] = useState('');
  const [st, setSt] = useState('');
  const [mt, setMt] = useState('');
  const [he, setHe] = useState<boolean|undefined>();
  const [detail, setDetail] = useState<ITraceDetail|null>(null);
  const [tab, setTab] = useState<'dashboard'|'detail'|'eval'>('dashboard');
  const [imp, setImp] = useState(false);
  const [red, setRed] = useState(false);
  const [ld, setLd] = useState(true);
  const [err, setErr] = useState<string|null>(null);

  useEffect(() => { init(); }, []);
  useEffect(() => { if (tab==='dashboard') load(); }, [page, st, mt, he, tab]);

  const init = async () => { setLd(true);
    try { setSession(await api.getMe()); setOverview(await api.getOverview()); await load(); }
    catch (e: any) { setErr(e.message || 'Init failed'); }
    finally { setLd(false); }
  };

  const load = async () => {
    try { const r = await api.getTraces({ search: search||undefined, status: st||undefined, model: mt||undefined, has_errors: he, limit: ps, offset: page*ps }); setTraces(r.items); setTotal(r.total); }
    catch (e: any) { setErr(e.message || 'Load failed'); }
  };

  const inspect = async (id: string) => { setLd(true); setErr(null);
    try { setDetail(await api.getTraceDetail(id)); setTab('detail'); }
    catch (e: any) { setErr(e.message || 'Detail error'); }
    finally { setLd(false); }
  };

  const del = async (id: string) => {
    if (!confirm(`Delete ${id}?`)) return;
    try { await api.deleteTrace(id); setTab('dashboard'); setDetail(null); await init(); }
    catch (e: any) { alert(`Delete failed: ${e.message}`); }
  };

  const sw = async (r: UserRole) => { try { setSession(await api.switchRole(r)); } catch (e: any) { alert(e.message); } };

  const u = session?.roles||[];
  const ad = u.includes('admin');
  const an = ad || u.includes('analyst');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <header className="border-b border-slate-800 bg-slate-900/90 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-mono font-bold text-white">Ω</div>
            <div><h1 className="text-base font-bold">Agent Trace Observatory</h1><div className="text-[11px] text-slate-400">Alan Vo | AI & Machine Learning</div></div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={()=>setTab('dashboard')} className={`px-3 py-1.5 text-xs rounded-lg transition ${tab==='dashboard'?'bg-indigo-600 text-white':'text-slate-400 hover:bg-slate-800'}`}>Dashboard</button>
            <button onClick={()=>setTab('eval')} className={`px-3 py-1.5 text-xs rounded-lg transition ${tab==='eval'?'bg-indigo-600 text-white':'text-slate-400 hover:bg-slate-800'}`}>AI/ML Evaluation</button>
            {ad && <button onClick={()=>setRed(true)} className="px-3 py-1.5 text-xs rounded-lg bg-amber-600 text-white hover:bg-amber-500">Redaction Rules</button>}
            {session?.demo_mode && <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 rounded-lg p-1 text-xs">{(['viewer','analyst','admin'] as UserRole[]).map(r=><button key={r} onClick={()=>sw(r)} className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize ${u.includes(r)?'bg-indigo-600 text-white font-semibold':'text-slate-400'}`}>{r}</button>)}</div>}
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto px-4 py-6 space-y-5">
        {err && <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs flex justify-between"><span>{err}</span><button onClick={()=>setErr(null)}>✕</button></div>}
        {tab==='detail' && detail ? <TraceDetail trace={detail} onBack={()=>setTab('dashboard')} onDelete={del} isAdmin={ad} /> :
        tab==='eval' ? <EvaluationView onBack={()=>setTab('dashboard')} canRunEvaluation={an} /> : (
          <div className="space-y-5">
            {overview && <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">{
              [{l:'Total Traces',v:overview.total_traces,c:'text-slate-100'},{l:'Failure Rate',v:`${(overview.overall_failure_rate*100).toFixed(1)}%`,c:'text-rose-400'},{l:'Total Tokens',v:overview.total_tokens_processed.toLocaleString(),c:'text-slate-100'},{l:'Cost (USD)',v:`$${overview.total_cost_usd.toFixed(4)}`,c:'text-emerald-400'},{l:'Avg Duration',v:`${overview.avg_latency_seconds.toFixed(2)}s`,c:'text-slate-100'},{l:'Redactions',v:overview.total_redactions,c:'text-amber-400'}].map((m,i)=><div key={i} className={`${B} p-3.5`}><div className="text-[11px] text-slate-400">{m.l}</div><div className={`text-lg font-bold font-mono mt-0.5 ${m.c}`}>{m.v}</div></div>)}
            </div>}
            <div className={`${B} p-3.5 flex flex-wrap items-center justify-between gap-3`}>
              <form onSubmit={e=>{e.preventDefault();setPage(0);load();}} className="flex flex-wrap items-center gap-2 flex-1">
                <input placeholder="Search traces..." value={search} onChange={e=>setSearch(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 w-44"/>
                <input placeholder="Filter model..." value={mt} onChange={e=>setMt(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-500 w-28"/>
                <select value={st} onChange={e=>setSt(e.target.value)} className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-300"><option value="">All Statuses</option><option value="completed">Completed</option><option value="failed">Failed</option></select>
                <select value={he===undefined?'':String(he)} onChange={e=>setHe(e.target.value===''?undefined:e.target.value==='true')} className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-300"><option value="">All Health</option><option value="true">Has Errors</option><option value="false">Healthy</option></select>
                <button type="submit" className={BS}>Filter</button>
              </form>
              <div className="flex items-center gap-2">
                <button onClick={()=>window.open('/api/export/traces?format=csv','_blank')} className={BS}>Export CSV</button>
                <button onClick={()=>window.open('/api/export/traces?format=json','_blank')} className={BS}>Export JSON</button>
                {an && <button onClick={()=>setImp(true)} className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 text-white hover:bg-indigo-500">+ Import Trace</button>}
              </div>
            </div>
            <div className={`${B} overflow-hidden`}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] border-b border-slate-800 uppercase"><tr>{['Trace ID','Agent','Goal','Status','Tokens','Cost','Duration','Redactions'].map(h=><th key={h} className="py-2 px-3">{h}</th>)}<th className="py-2 px-3 text-right">Action</th></tr></thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {traces.length===0 ? <tr><td colSpan={9} className="py-8 text-center text-slate-500 font-sans">{ld?'Loading...':'No traces found.'}</td></tr> : traces.map(t=><tr key={t.trace_id} className="hover:bg-slate-800/40 cursor-pointer" onClick={()=>inspect(t.trace_id)}>
                      <td className="py-2 px-3 text-indigo-300 font-semibold">{t.trace_id}</td>
                      <td className="py-2 px-3 font-sans text-slate-200">{t.agent_name}</td>
                      <td className="py-2 px-3 font-sans max-w-xs truncate text-slate-400">{t.root_goal}</td>
                      <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${t.status==='completed'?'bg-emerald-500/10 text-emerald-400':'bg-rose-500/10 text-rose-400'}`}>{t.status}</span></td>
                      <td className="py-2 px-3 text-slate-400">{t.total_tokens.toLocaleString()}</td>
                      <td className="py-2 px-3 text-emerald-400">${t.total_cost_usd.toFixed(5)}</td>
                      <td className="py-2 px-3 text-slate-400">{t.duration_seconds.toFixed(2)}s</td>
                      <td className="py-2 px-3 text-amber-400">{t.redactions_count}</td>
                      <td className="py-2 px-3 text-right"><button onClick={e=>{e.stopPropagation();inspect(t.trace_id);}} className="px-2 py-1 rounded bg-slate-800 text-[11px] hover:bg-indigo-600">Inspect</button></td>
                    </tr>)}
                  </tbody>
                </table>
              </div>
              {total>ps && <div className="p-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400"><span>Showing {page*ps+1}–{Math.min((page+1)*ps,total)} of {total}</span><div className="flex gap-2"><button onClick={()=>setPage(p=>Math.max(0,p-1))} disabled={page===0} className="px-2 py-1 rounded bg-slate-800 disabled:opacity-40">Prev</button><button onClick={()=>setPage(p=>p+1)} disabled={(page+1)*ps>=total} className="px-2 py-1 rounded bg-slate-800 disabled:opacity-40">Next</button></div></div>}
            </div>
          </div>
        )}
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-500">Agent Trace Observatory \u00A9 2026 Alan Vo <a href="mailto:alanvo@gmail.com" className="text-indigo-400">alanvo@gmail.com</a></footer>
      <TraceImportModal isOpen={imp} onClose={()=>setImp(false)} onSuccess={()=>{load();api.getOverview().then(setOverview);}} />
      <RedactionRulesManager isOpen={red} onClose={()=>setRed(false)} />
    </div>
  );
};