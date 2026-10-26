import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET as diff } from '../src/app/api/history/diff/route';
import { GET as workspace } from '../src/app/api/workspace/route';
import { historicalValue, reportVersionLink, changeLabels } from '../src/lib/history-types';
const before = '11111111-1111-4111-8111-111111111111';
const after = '22222222-2222-4222-8222-222222222222';
const query = `before_run=${before}&after_run=${after}&before_version=2&after_version=1`;
afterEach(() => { vi.unstubAllGlobals(); });
it('BFF-H01: private comparison never dispatches without a session', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  expect((await diff(new NextRequest(`http://localhost/api/history/diff?${query}`))).status).toBe(401);
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-H02: invalid IDs/versions do not fall back to another report or arbitrary upstream URL', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  for (const bad of [query.replace(before, 'https://example.invalid'), query.replace('before_version=2', 'before_version=0'), query.replace('after_version=1', 'after_version=-1')])
    expect((await diff(new NextRequest(`http://localhost/api/history/diff?${bad}`))).status).toBe(400);
  for (const bad of ['report_version=1', `run_id=${before}&report_version=`, `run_id=${before}&report_version=0`])
    expect((await workspace(new NextRequest(`http://localhost/api/workspace?${bad}`))).status).toBe(400);
  expect(fetch).not.toHaveBeenCalled();
});
it('BFF-H03: exact immutable selectors survive the proxy and unrelated query arguments are stripped', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ label: 'DEMO' }), { headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetch);
  const response = await diff(new NextRequest(`http://localhost/api/history/diff?${query}&upstream=https://example.invalid`, { headers: { Cookie: 'lather_session=DEMO-cookie' } }));
  expect(response.status).toBe(200); expect(response.headers.get('cache-control')).toBe('no-store');
  expect(fetch.mock.calls[0][0]).toMatch(new RegExp(`/api/history/diff\\?${query}$`));
  expect(fetch.mock.calls[0][0]).not.toContain('example.invalid');
});
it('UI-H01: unavailable values and source-reported disappearance are explicit; links pin exact versions', () => {
  expect(historicalValue({ amount: null, currency: 'INR', total_weight_g: null, pack_qty: null, unit_price_100g: null })).toContain('Price unavailable');
  expect(historicalValue({ amount: '0', currency: 'INR', total_weight_g: '100', pack_qty: 1, unit_price_100g: '0' })).toContain('0 INR');
  expect(changeLabels.gone).toContain('source reports'); expect(changeLabels.new).toBe('Newly observed');
  expect(reportVersionLink(before, 2)).toBe(`/report?run=${before}&version=2`);
});
