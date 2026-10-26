import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { POST as save } from '../src/app/api/briefs/route';
import { POST as signIn } from '../src/app/api/session/route';
import { authConfig } from '../src/lib/server-api';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
it('BFF-01: cross-origin writes fail before authentication or upstream traffic', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  for (const handler of [save, signIn]) {
    const response = await handler(new NextRequest('http://127.0.0.1:3140/api/briefs', { method: 'POST', headers: { Host: '127.0.0.1:3140', Origin: 'https://example.invalid' } }));
    expect(response.status).toBe(403);
  }
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-02: unauthenticated save fails closed without traffic', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  const response = await save(new NextRequest('http://127.0.0.1:3140/api/briefs', { method: 'POST', headers: { Host: '127.0.0.1:3140', Origin: 'http://127.0.0.1:3140' } }));
  expect(response.status).toBe(401); expect(fetch).not.toHaveBeenCalled();
});
it('BFF-03: non-public key classification is rejected', () => {
  vi.stubEnv('LATHER_SUPABASE_URL', 'http://127.0.0.1:57421');
  vi.stubEnv('LATHER_SUPABASE_PUBLISHABLE_KEY', 'DEMO-invalid-key');
  expect(authConfig()).toBeNull();
});
it('BFF-04: unavailable upstream does not disclose its exception or token', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('DEMO-private-upstream-detail')));
  const response = await save(new NextRequest('http://127.0.0.1:3140/api/briefs', { method: 'POST', headers: {
    Host: '127.0.0.1:3140', Origin: 'http://127.0.0.1:3140', Cookie: 'lather_session=DEMO-token', 'Idempotency-Key': 'DEMO-retry-key', 'Content-Type': 'application/json',
  }, body: JSON.stringify({ category: 'DEMO soap' }) }));
  expect(response.status).toBe(503);
  const body = await response.text();
  expect(body).not.toContain('DEMO-private-upstream-detail'); expect(body).not.toContain('DEMO-token');
  expect(response.headers.get('cache-control')).toBe('no-store');
});
