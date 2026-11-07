/** Redaction Rules for admins. */
import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { RedactionRule, RedactionTestRequest, RedactionTestResponse } from '../types';

interface P { isOpen: boolean; onClose: () => void; }
const C = ['SECRET_KEY','PII','NETWORK_PII','FINANCIAL_PII','CUSTOM'] as const;

export const RedactionRulesManager: React.FC<P> = ({ isOpen, onClose }) => {
  const [rs, setRs] = useState<RedactionRule[]>([]);
  const [ld, setLd] = useState(true);
  const [er, setEr] = useState<string|null>(null);
  const [fe, setFe] = useState<string|null>(null);
  const [fm, setFm] = useState<Omit<RedactionRule,'id'|'created_at'|'updated_at'|'is_builtin'>>({
    rule_name: '', pattern: '', replacement: '', category: 'SECRET_KEY', pattern_type: 'regex', enabled: true
  });
  const [te, setTe] = useState<{rule: RedactionRule|null; req: RedactionTestRequest; res: RedactionTestResponse|null; loading: boolean}|null>(null);
  const [ter, setTer] = useState<string|null>(null);

  useEffect(() => { if (isOpen) load(); }, [isOpen]);

  const load = async () => { setLd(true); setEr(null);
    try { setRs(await api.getRedactionRules()); } catch (e: any) { setEr(e.message || 'Load failed'); } finally { setLd(false); }
  };

  const save = async (e: React.FormEvent) => { e.preventDefault(); setFe(null);
    try { ed ? await api.updateRedactionRule(ed.id, fm) : await api.createRedactionRule(fm); setEd(null); reset(); load(); }
    catch (e: any) { setFe(e.message || 'Save failed'); }
  };

  const del = async (id: number) => { if (!confirm('Delete?')) return;
    try { await api.deleteRedactionRule(id); load(); } catch (e: any) { setEr(e.message || 'Del failed'); }
  };

  const edit = (r: RedactionRule) => { setEd(r); setFm({rule_name:r.rule_name, pattern:r.pattern, replacement:r.replacement, category:r.category, pattern_type:r.pattern_type, enabled:r.enabled}); };
  const openTest = (r: RedactionRule) => {
    setTe({ rule: r, req: { pattern: r.pattern, pattern_type: r.pattern_type, sample_text: '' }, res: null, loading: false });
    setTer(null);
  };

  const runTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!te) return;
    setTer(null);
    setTe(t => t ? {...t, loading: true} : null);
    try {
      const res = await api.testRedactionPattern(te.req);
      setTe(t => t ? {...t, res, loading: false} : null);
    } catch (e: any) {
      setTer(e.message || 'Test failed');
      setTe(t => t ? {...t, loading: false} : null);
    }
  };

  const closeTest = () => { setTe(null); setTer(null); };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        <div className="flex justify-between p-4 border-b border-slate-800"><div><h3 className="font-semibold">Redaction Rules</h3><p className="text-xs text-slate-400">Custom regex/literal patterns. Built-in are read-only.</p></div><button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button></div>
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {er && <div className="p-2 text-xs bg-rose-950/60 border border-rose-800 text-rose-300 rounded">{er}</div>}
          <div className="bg-slate-950/60 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-3 border-b border-slate-800 flex justify-between"><h4 className="font-semibold text-sm">Rules</h4><button onClick={()=>{reset();setEd(null);}} className="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500">+ Add</button></div>
            <div className="overflow-x-auto"><table className="w-full text-xs text-slate-300"><thead className="bg-slate-900 text-slate-400 font-mono text-[11px] border-b border-slate-800 uppercase"><tr>{['Name','Pattern','Replacement','Category','Type','Status','Built-in','Actions'].map(h=><th key={h} className="py-1 px-2">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">{ld ? <tr><td colSpan={8} className="py-4 text-center text-slate-500">Loading...</td></tr> : !rs.length ? <tr><td colSpan={8} className="py-4 text-center text-slate-500">No custom rules</td></tr> : rs.map(r => <tr key={r.id} className="hover:bg-slate-800/40"><td className="py-1 px-2 text-indigo-300 font-semibold">{r.rule_name}</td><td className="py-1 px-2 text-slate-400 max-w-xs truncate" title={r.pattern}>{r.pattern}</td><td className="py-1 px-2 text-slate-400 max-w-xs truncate" title={r.replacement}>{r.replacement}</td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] border ${r.category==='SECRET_KEY'?'bg-rose-500/10 text-rose-400 border-rose-500/20':r.category==='PII'?'bg-amber-500/10 text-amber-400 border-amber-500/20':r.category==='NETWORK_PII'?'bg-blue-500/10 text-blue-400 border-blue-500/20':r.category==='FINANCIAL_PII'?'bg-emerald-500/10 text-emerald-400 border-emerald-500/20':'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{r.category}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] border ${r.pattern_type==='regex'?'bg-indigo-500/10 text-indigo-400 border-indigo-500/20':'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{r.pattern_type}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] ${r.enabled?'bg-emerald-500/10 text-emerald-400':'bg-rose-500/10 text-rose-400'}`}>{r.enabled?'On':'Off'}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] ${r.is_builtin?'bg-amber-500/10 text-amber-400 border border-amber-500/20':'bg-emerald-500/10 text-emerald-400'}`}>{r.is_builtin?'Yes':'No'}</span></td><td className="py-1 px-2 text-right">{!r.is_builtin && <> <button onClick={()=>edit(r)} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] hover:bg-indigo-600 mr-1">Edit</button> <button onClick={()=>openTest(r)} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] hover:bg-blue-600 text-blue-400 mr-1">Test</button> <button onClick={()=>del(r.id)} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] hover:bg-rose-600 text-rose-400">Del</button> </>}</td></tr>)}</tbody></table></div></div>
          {te && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl w-full max-w-md p-4 space-y-3">
              <div className="flex justify-between items-center"><h4 className="font-semibold">Test Pattern: {te.rule?.rule_name}</h4><button onClick={closeTest} className="text-slate-400 hover:text-slate-200">✕</button></div>
              <form onSubmit={runTest} className="space-y-3">
                {ter && <div className="p-2 text-xs bg-rose-950/60 border border-rose-800 text-rose-300 rounded">{ter}</div>}
                <div><label className="block text-xs text-slate-400 mb-0.5">Pattern</label><textarea value={te.req.pattern} onChange={e=>setTe(t=>t?{...t, req:{...t.req, pattern:e.target.value}}:null)} rows={2} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 font-mono focus:ring-indigo-500 focus:ring-1 outline-none" disabled={te.loading} required/></div>
                <div className="grid sm:grid-cols-2 gap-3"><div><label className="block text-xs text-slate-400 mb-0.5">Type</label><select value={te.req.pattern_type} onChange={e=>setTe(t=>t?{...t, req:{...t.req, pattern_type:e.target.value as 'regex'|'literal'}}:null)} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 focus:ring-indigo-500 focus:ring-1 outline-none" disabled={te.loading}><option value="regex">Regex</option><option value="literal">Literal</option></select></div><div><label className="block text-xs text-slate-400 mb-0.5">Sample Text</label><textarea value={te.req.sample_text} onChange={e=>setTe(t=>t?{...t, req:{...t.req, sample_text:e.target.value}}:null)} rows={3} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 focus:ring-indigo-500 focus:ring-1 outline-none" disabled={te.loading} placeholder="Paste text to test against..."/></div></div>
                <div className="flex justify-end gap-2"><button type="button" onClick={closeTest} className="px-3 py-1.5 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700" disabled={te.loading}>Close</button><button type="submit" className="px-3 py-1.5 text-xs font-semibold rounded bg-blue-600 text-white hover:bg-blue-500" disabled={te.loading}>{te.loading?'Testing...':'Run Test'}</button></div>
              </form>
              {te.res && <div className="border-t border-slate-800 pt-3 space-y-2"><h5 className="font-semibold text-xs text-slate-400">Results</h5><div className="text-xs text-slate-300">{te.res.pattern_valid?'Valid pattern':'Invalid pattern'}{te.res.error && <span className="text-rose-400 ml-2">Error: {te.res.error}</span>}</div><div className="text-xs text-slate-400">Sanitized: <code className="text-slate-300 bg-slate-900/50 px-1 rounded">{te.res.sanitized_text}</code></div><div className="text-xs text-slate-400">Matches ({te.res.matches.length})</div><div className="p-2 bg-slate-900/50 border border-slate-800 rounded font-mono text-[10px] max-h-40 overflow-auto">{te.res.matches.map((m,i)=>(<div key={i}>• "{m.match}" at {m.start}-{m.end}</div>))}</div></div>}
            </div>
          </div>}
        </div>
      </div>
    </div>
  );
};