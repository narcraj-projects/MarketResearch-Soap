import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST } from '../src/app/api/runs/[...path]/route';
import { GET as workspace } from '../src/app/api/workspace/route';
import { barPercent, percent, displayValue, eventSummary } from '../src/lib/run-api';
const id = '11111111-1111-4111-8111-111111111111';
const context = (action: string) => ({ params: Promise.resolve({ path: [id, action] }) });
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
it('UI-R02: persisted activity explains recorded events without adding outcomes or dumping internal IDs', () => {
  expect(eventSummary('workflow.node', { node: 'research', label: 'DEMO' })).toBe('Completed research.');
  expect(eventSummary('approval.pending', { gate: 'report' })).toBe('Waiting for final report review.');
  expect(eventSummary('tool.completed', { tool: 'public.retrieve', code: 'access_denied', operation_id: 'DEMO-internal' })).toBe('public retrieve: access denied.');
  expect(eventSummary('custom.unknown', {})).toBe('custom unknown recorded.');
});
it('UI-R01: unknown prices remain missing, real zero remains zero and currencies can use separate scales', () => {
  expect(barPercent(null, 100)).toBeNull(); expect(barPercent('NaN', 100)).toBeNull(); expect(barPercent('-5', 100)).toBeNull();
  expect(barPercent('0', 100)).toBe(0); expect(barPercent('50', 100)).toBe(50); expect(barPercent('50', 200)).toBe(25);
  expect(percent(null)).toBe('\u2014'); expect(percent(0)).toBe('0%'); expect(displayValue(null)).toBe('Unavailable');
});
it('BFF-R01: malformed IDs, unsupported exports and unlisted actions never dispatch', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect((await workspace(new NextRequest('http://localhost/api/workspace?run_id=invalid'))).status).toBe(404);
  expect((await GET(new NextRequest('http://localhost/api/runs'), context('secrets'))).status).toBe(404);
  expect((await GET(new NextRequest('http://localhost/api/runs?format=pdf&report_id=' + id), context('export'))).status).toBe(400);
  expect((await POST(new NextRequest('http://localhost/api/runs', { method: 'POST' }), context('save'))).status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-R02: report approval requires same origin, session and request key before dispatch', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  for (const [headers, status] of [
    [{ Origin: 'https://example.invalid', Host: 'localhost' }, 403],
    [{ Origin: 'http://localhost', Host: 'localhost' }, 401],
    [{ Origin: 'http://localhost', Host: 'localhost', Cookie: 'lather_session=DEMO-token' }, 400],
  ] as const) expect((await POST(new NextRequest('http://localhost/api/runs', { method: 'POST', headers }), context('report-decision'))).status).toBe(status);
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-R03: download preserves bytes, strips private headers, prevents caching and redirects', async () => {
  const bytes = 'DEMO,unavailable,not adjudicated\r\n';
  const fetch = vi.fn().mockResolvedValue(new Response(bytes, { headers: { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="DEMO.csv"', 'X-Private': 'DEMO-private' } }));
  vi.stubGlobal('fetch', fetch);
  const response = await GET(new NextRequest(`http://localhost/api/runs?format=csv&report_id=${id}`, { headers: { Cookie: 'lather_session=DEMO-token' } }), context('export'));
  expect(await response.text()).toBe(bytes); expect(response.headers.get('x-private')).toBeNull(); expect(response.headers.get('cache-control')).toBe('no-store');
  const options = fetch.mock.calls[0][1]; expect(options.redirect).toBe('error'); expect(options.cache).toBe('no-store');
  expect(response.headers.get('content-security-policy')).toContain("default-src 'none'");
});
