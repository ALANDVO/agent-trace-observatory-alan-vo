/** Typed API client. */
import { AdvisoryResponse, AggregateStats, EvaluationRun, RedactionRule, RedactionTestRequest, RedactionTestResponse, TraceDetail, TraceSummary, UserRole, UserSession } from './types';
let csrf = '';

async function req<T>(p: string, o: RequestInit = {}): Promise<T> {
  const h = new Headers(o.headers);
  h.set('Accept', 'application/json');
  if (o.body && typeof o.body === 'string' && !h.has('Content-Type')) h.set('Content-Type', 'application/json');
  if (csrf && !h.has('X-CSRF-Token')) h.set('X-CSRF-Token', csrf);
  const r = await fetch(p, { ...o, headers: h, credentials: 'include' });
  if (!r.ok) {
    const t = await r.text(); let m = t;
    try { m = JSON.parse(t).detail || t; } catch {}
    throw new Error(typeof m === 'string' ? m : 'Request failed');
  }
  if (r.status === 204) return {} as T;
  return r.json();
}

export const api = {
  async getMe(): Promise<UserSession> { const d = await req<UserSession>('/api/auth/me'); csrf = d.csrf_token; return d; },
  async switchRole(r: UserRole) { const d = await req<UserSession>('/api/auth/demo-switch-role', { method: 'POST', body: JSON.stringify({ role: r }) }); csrf = d.csrf_token; return d; },
  getOverview: () => req<AggregateStats>('/api/analytics/overview'),
  getTraces: (p: { agent_name?: string; status?: string; model?: string; has_errors?: boolean; search?: string; limit?: number; offset?: number }) => req<{ items: TraceSummary[]; total: number; limit: number; offset: number }>('/api/traces', { method: 'POST', body: JSON.stringify(p) }),
  getTraceDetail: (id: string) => req<TraceDetail>(`/api/traces/${encodeURIComponent(id)}`),
  importTrace: (pl: any) => req<TraceDetail>('/api/traces', { method: 'POST', body: JSON.stringify(pl) }),
  deleteTrace: (id: string) => req<void>(`/api/traces/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getAdvisory: (id: string, cp?: string) => req<AdvisoryResponse>(`/api/traces/${encodeURIComponent(id)}/advisory`, { method: 'POST', body: JSON.stringify({ custom_prompt: cp }) }),
  runBenchmark: () => req<EvaluationRun>('/api/evaluation/run', { method: 'POST' }),
  getBenchmarkDataset: () => req<{ dataset_name: string; total_samples: number; samples: any[] }>('/api/evaluation/dataset'),
  getRedactionRules: () => req<RedactionRule[]>('/api/redaction/rules'),
  createRedactionRule: (r: Omit<RedactionRule, 'id'|'created_at'|'updated_at'|'is_builtin'>) => req<RedactionRule>('/api/redaction/rules', { method: 'POST', body: JSON.stringify(r) }),
  updateRedactionRule: (id: number, r: Partial<Omit<RedactionRule, 'id'|'created_at'|'updated_at'|'is_builtin'>>) => req<RedactionRule>(`/api/redaction/rules/${id}`, { method: 'PUT', body: JSON.stringify(r) }),
  deleteRedactionRule: (id: number) => req<void>(`/api/redaction/rules/${id}`, { method: 'DELETE' }),
  testRedactionPattern: (t: RedactionTestRequest) => req<RedactionTestResponse>('/api/redaction/rules/test', { method: 'POST', body: JSON.stringify(t) }),
};