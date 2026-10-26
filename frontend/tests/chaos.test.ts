import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET } from '../src/app/api/chaos/capabilities/route';
import { POST } from '../src/app/api/chaos/runs/route';
import { eventSummary } from '../src/lib/run-api';
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
it('BFF-C01: chaos writes require same origin, session and key before dispatch', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  for (const [headers, status] of [
    [{ Origin: 'https://example.invalid', Host: 'localhost' }, 403],
    [{ Origin: 'http://localhost', Host: 'localhost' }, 401],
    [{ Origin: 'http://localhost', Host: 'localhost', Cookie: 'lather_session=DEMO-token' }, 400],
  ] as const) expect((await POST(new NextRequest('http://localhost/api/chaos/runs', { method: 'POST', headers }))).status).toBe(status);
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-C02: server capability/denial pass through without trusting client environment flags', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ enabled: false, label: 'DEMO', scenarios: [] }))));
  const response = await GET(new NextRequest('http://localhost/api/chaos/capabilities?enabled=true', { headers: { Cookie: 'lather_session=DEMO-token' } }));
  expect(await response.json()).toEqual({ enabled: false, label: 'DEMO', scenarios: [] });
  expect(response.headers.get('cache-control')).toBe('no-store');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"chaos_disabled"}', { status: 403 })));
  const denied = await POST(new NextRequest('http://localhost/api/chaos/runs', { method: 'POST', headers: {
    Host: 'localhost', Origin: 'http://localhost', Cookie: 'lather_session=DEMO-token', 'Idempotency-Key': 'DEMO-key', 'Content-Type': 'application/json',
  }, body: '{"scenario":"timeout"}' }));
  expect(denied.status).toBe(403);
});
it('UI-C01: events distinguish saved recovery from configuration and unresolved failure', () => {
  expect(eventSummary('chaos.armed', { scenario: 'timeout' })).toContain('configured');
  expect(eventSummary('tool.retryable_failure', { tool: 'public.search', code: 'timeout', attempt: 1, retry_limit: 3 })).toBe('public.search: timeout; attempt 1 recorded (limit 3).');
  expect(eventSummary('tool.recovered', { tool: 'public.search', attempt: 2 })).toContain('recovered on recorded attempt 2');
  expect(eventSummary('model.output_invalid', { attempt: 1 })).toContain('failed JSON/schema');
  expect(eventSummary('model.replay_validated', { repaired: true })).toContain('no provider call');
  expect(eventSummary('analysis.reviewed', { decision: 'unresolved' })).toContain('unresolved');
  expect(eventSummary('chaos.worker_recovered', { preserved_lanes: 1 })).toContain('1 saved lane reused');
});
