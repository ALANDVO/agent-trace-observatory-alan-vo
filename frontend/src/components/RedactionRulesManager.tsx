/** Redaction Rules for admins. */
import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { RedactionRule } from '../types';

interface P { isOpen: boolean; onClose: () => void; }
const C = ['SECRET_KEY','PII','NETWORK_PII','FINANCIAL_PII','CUSTOM'] as const;

export const RedactionRulesManager: React.FC<P> = ({ isOpen, onClose }) => {
  const [rs, setRs] = useState<RedactionRule[]>([]);
  const [ld, setLd] = useState(true);
  const [er, setEr] = useState<string|null>(null);
  const [ed, setEd] = useState<RedactionRule|null>(null);
  const [fm, setFm] = useState<Omit<RedactionRule,'id'|'created_at'|'updated_at'|'is_builtin'>>({
    rule_name: '', pattern: '', replacement: '', category: 'SECRET_KEY', pattern_type: 'regex', enabled: true
  });
  const [fe, setFe] = useState<string|null>(null);

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
  const reset = () => { setFm({rule_name:'', pattern:'', replacement:'', category:'SECRET_KEY', pattern_type:'regex', enabled:true}); };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        <div className="flex justify-between p-4 border-b border-slate-800"><div><h3 className="font-semibold">Redaction Rules</h3><p className="text-xs text-slate-400">Custom regex/literal patterns. Built-in are read-only.</p></div><button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button></div>
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {er && <div className="p-2 text-xs bg-rose-950/60 border border-rose-800 text-rose-300 rounded">{er}</div>}
          <div className="bg-slate-950/60 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-3 border-b border-slate-800 flex justify-between"><h4 className="font-semibold text-sm">Rules</h4><button onClick={()=>{reset();setEd(null);}} className="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500">+ Add</button></div>
            <div className="overflow-x-auto"><table className="w-full text-xs text-slate-300"><thead className="bg-slate-900 text-slate-400 font-mono text-[11px] border-b border-slate-800 uppercase"><tr>{['Name','Pattern','Replacement','Category','Type','Status','Built-in','Actions'].map(h=><th key={h} className="py-1 px-2">{h}</th>)}</tr></thead><tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">{ld ? <tr><td colSpan={8} className="py-4 text-center text-slate-500">Loading...</td></tr> : !rs.length ? <tr><td colSpan={8} className="py-4 text-center text-slate-500">No custom rules</td></tr> : rs.map(r => <tr key={r.id} className="hover:bg-slate-800/40"><td className="py-1 px-2 text-indigo-300 font-semibold">{r.rule_name}</td><td className="py-1 px-2 text-slate-400 max-w-xs truncate" title={r.pattern}>{r.pattern}</td><td className="py-1 px-2 text-slate-400 max-w-xs truncate" title={r.replacement}>{r.replacement}</td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] border ${r.category==='SECRET_KEY'?'bg-rose-500/10 text-rose-400 border-rose-500/20':r.category==='PII'?'bg-amber-500/10 text-amber-400 border-amber-500/20':r.category==='NETWORK_PII'?'bg-blue-500/10 text-blue-400 border-blue-500/20':r.category==='FINANCIAL_PII'?'bg-emerald-500/10 text-emerald-400 border-emerald-500/20':'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{r.category}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] border ${r.pattern_type==='regex'?'bg-indigo-500/10 text-indigo-400 border-indigo-500/20':'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>{r.pattern_type}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] ${r.enabled?'bg-emerald-500/10 text-emerald-400':'bg-rose-500/10 text-rose-400'}`}>{r.enabled?'On':'Off'}</span></td><td className="py-1 px-2"><span className={`px-1 py-0.5 rounded text-[10px] ${r.is_builtin?'bg-amber-500/10 text-amber-400 border border-amber-500/20':'bg-emerald-500/10 text-emerald-400'}`}>{r.is_builtin?'Yes':'No'}</span></td><td className="py-1 px-2 text-right">{!r.is_builtin && <> <button onClick={()=>edit(r)} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] hover:bg-indigo-600 mr-1">Edit</button> <button onClick={()=>del(r.id)} className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] hover:bg-rose-600 text-rose-400">Del</button> </>}</td></tr>)}</tbody></table></div></div>
          {(ed || !rs.some(r=>!r.is_builtin)) && <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4 space-y-3"><h4 className="font-semibold text-sm">{ed?'Edit':'Create'} Rule</h4><form onSubmit={save} className="space-y-3">{fe && <div className="p-2 text-xs bg-rose-950/60 border border-rose-800 text-rose-300 rounded">{fe}</div>}<div className="grid sm:grid-cols-2 gap-3"><div><label className="block text-xs text-slate-400 mb-0.5">Name*</label><input value={fm.rule_name} onChange={e=>setFm({...fm,rule_name:e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 focus:ring-indigo-500 focus:ring-1 outline-none" disabled={!!ed} required pattern="^[a-zA-Z0-9_-]+$" placeholder="my-token"/></div><div><label className="block text-xs text-slate-400 mb-0.5">Category</label><select value={fm.category} onChange={e=>setFm({...fm,category:e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 focus:ring-indigo-500 focus:ring-1 outline-none">{C.map(c=><option key={c} value={c}>{c}</option>)}</select></div></div><div><label className="block text-xs text-slate-400 mb-0.5">Pattern*</label><textarea value={fm.pattern} onChange={e=>setFm({...fm,pattern:e.target.value})} rows={2} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 font-mono focus:ring-indigo-500 focus:ring-1 outline-none" placeholder={fm.pattern_type==='regex'?'\\bTOKEN_[A-Z0-9]{24}\\b':'LITERAL'} required/></div><div><label className="block text-xs text-slate-400 mb-0.5">Replacement*</label><input value={fm.replacement} onChange={e=>setFm({...fm,replacement:e.target.value})} className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-xs text-slate-200 focus:ring-indigo-500 focus:ring-1 outline-none" placeholder="[REDACTED:MY_TOKEN]" required/></div><div className="flex items-center gap-4"><label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={fm.enabled} onChange={e=>setFm({...fm,enabled:e.target.checked})} className="w-3 h-3 rounded border-slate-600 text-indigo-600 focus:ring-indigo-500"/>Enabled</label><label className="flex items-center gap-1.5 text-xs text-slate-300"><select value={fm.pattern_type} onChange={e=>setFm({...fm,pattern_type:e.target.value as 'regex'|'literal'})} className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200"><option value="regex">Regex</option><option value="literal">Literal</option></select></label></div><div className="flex justify-end gap-2 pt-1"><button type="button" onClick={()=>{setEd(null);reset();}} className="px-3 py-1.5 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700">Cancel</button><button type="submit" className="px-3 py-1.5 text-xs font-semibold rounded bg-indigo-600 text-white hover:bg-indigo-500">{ed?'Update':'Create'}</button></div></form></div>}
        </div>
      </div>
    </div>
  );
};