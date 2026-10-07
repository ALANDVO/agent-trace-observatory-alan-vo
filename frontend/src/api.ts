/** Typed API client communicating with backend observatory services. */

import {
  AdvisoryResponse,
  AggregateStats,
  EvaluationRun,
  TraceDetail,
  TraceSummary,
  UserRole,
  UserSession
} from './types';

let cachedCsrfToken = '';

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set('Accept', 'application/json');

  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  if (cachedCsrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', cachedCsrfToken);
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: 'include'
  });

  if (!response.ok) {
    let errMsg = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  async getMe(): Promise<UserSession> {
    const session = await request<UserSession>('/api/auth/me');
    if (session.csrf_token) {
      cachedCsrfToken = session.csrf_token;
    }
    return session;
  },

  async switchRole(role: UserRole): Promise<UserSession> {
    const session = await request<UserSession>('/api/auth/demo-switch-role', {
      method: 'POST',
      body: JSON.stringify({ role })
    });
    if (session.csrf_token) {
      cachedCsrfToken = session.csrf_token;
    }
    return session;
  },

  async getOverview(): Promise<AggregateStats> {
    return request<AggregateStats>('/api/analytics/overview');
  },

  async getTraces(params: {
    agent_name?: string; status?: string; model?: string; has_errors?: boolean; search?: string; limit?: number; offset?: number;
  }): Promise<{ items: TraceSummary[]; total: number; limit: number; offset: number }> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
    const qs = q.toString();
    return request<{ items: TraceSummary[]; total: number; limit: number; offset: number }>(`/api/traces${qs ? `?${qs}` : ''}`);
  },

  async getTraceDetail(traceId: string): Promise<TraceDetail> {
    return request<TraceDetail>(`/api/traces/${encodeURIComponent(traceId)}`);
  },

  async importTrace(payload: any): Promise<TraceDetail> {
    return request<TraceDetail>('/api/traces', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },

  async deleteTrace(traceId: string): Promise<void> {
    return request<void>(`/api/traces/${encodeURIComponent(traceId)}`, {
      method: 'DELETE'
    });
  },

  async getAdvisory(traceId: string, customPrompt?: string): Promise<AdvisoryResponse> {
    return request<AdvisoryResponse>(`/api/traces/${encodeURIComponent(traceId)}/advisory`, {
      method: 'POST',
      body: JSON.stringify({ custom_prompt: customPrompt })
    });
  },

  async runBenchmark(): Promise<EvaluationRun> {
    return request<EvaluationRun>('/api/evaluation/run', {
      method: 'POST'
    });
  },

  async getBenchmarkDataset(): Promise<{ dataset_name: string; total_samples: number; samples: any[] }> {
    return request<{ dataset_name: string; total_samples: number; samples: any[] }>('/api/evaluation/dataset');
  }
};
