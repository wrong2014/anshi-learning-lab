import type {
  APIAnswerRequest,
  APIAnswerResponse,
  APIStartResponse,
  ProviderStatus,
  ResultBranchCatalog,
  ResultData,
  StoredSessionDetail,
  StoredSessionSummary,
} from './types';

export async function startSession(): Promise<APIStartResponse> {
  const res = await fetch('/api/start');
  if (!res.ok) {
    throw new Error(`Failed to start session: ${res.status}`);
  }
  return res.json();
}

export async function submitAnswer(req: APIAnswerRequest): Promise<APIAnswerResponse> {
  const res = await fetch('/api/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit answer: ${res.status}`);
  }
  return res.json();
}

export async function listSessions(): Promise<StoredSessionSummary[]> {
  const res = await fetch('/api/sessions');
  if (!res.ok) {
    throw new Error(`Failed to list sessions: ${res.status}`);
  }
  const data = await res.json();
  return data.sessions || [];
}

export async function getSession(sessionId: string): Promise<StoredSessionDetail> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
  if (!res.ok) {
    throw new Error(`Failed to load session: ${res.status}`);
  }
  return res.json();
}

export async function getProviderStatus(): Promise<ProviderStatus> {
  const res = await fetch('/api/status');
  if (!res.ok) {
    throw new Error(`Failed to load provider status: ${res.status}`);
  }
  return res.json();
}

export async function getResultBranches(): Promise<ResultBranchCatalog> {
  const res = await fetch('/api/result-branches');
  if (!res.ok) {
    throw new Error(`Failed to load result branches: ${res.status}`);
  }
  return res.json();
}

export async function getResultPreview(request: {
  subject: string;
  category: string;
  amplifier?: string;
  grade_label?: string;
}): Promise<ResultData> {
  const res = await fetch('/api/result-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new Error(`Failed to load result preview: ${res.status}`);
  }
  const data = await res.json();
  return data.result;
}
