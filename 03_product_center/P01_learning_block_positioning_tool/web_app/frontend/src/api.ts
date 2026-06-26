import type { APIStartResponse, APIAnswerRequest, APIAnswerResponse } from './types';

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
