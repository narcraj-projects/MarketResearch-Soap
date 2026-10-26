import { expect, it } from 'vitest';
import { boundedJson, InputLimit, InvalidJson, LoginLimiter } from '../src/lib/ingress';
import { POST } from '../src/app/api/briefs/route';
import { NextRequest } from 'next/server';

it('SEC-BFF01: counts streamed bytes without trusting Content-Length', async () => {
  const stream = new ReadableStream({ start(c) { c.enqueue(new Uint8Array(33000)); c.enqueue(new Uint8Array(33000)); c.close(); } });
  const request = new Request('http://localhost', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: stream, duplex: 'half' } as RequestInit);
  await expect(boundedJson(request)).rejects.toBeInstanceOf(InputLimit);
});
it('SEC-BFF02: oversize authenticated brief fails before upstream dispatch', async () => {
  const response = await POST(new NextRequest('http://127.0.0.1:3140/api/briefs', { method: 'POST', headers: {
    Host: '127.0.0.1:3140', Origin: 'http://127.0.0.1:3140', Cookie: 'lather_session=DEMO-token', 'Idempotency-Key': 'DEMO-save-key', 'Content-Type': 'application/json',
  }, body: JSON.stringify({ objective: 'x'.repeat(70000) }) }));
  expect(response.status).toBe(413); expect(await response.text()).not.toContain('DEMO-token');
});
it('SEC-BFF03: login valve has fixed bounded state and expires', () => {
  let now = 60000; const limiter = new LoginLimiter(() => now, 2);
  expect(limiter.allow()).toBe(true); expect(limiter.allow()).toBe(true); expect(limiter.allow()).toBe(false);
  now += 60000; expect(limiter.allow()).toBe(true);
});
it('SEC-BFF04: malformed input is a client error without reflecting its content', async () => {
  const request = new Request('http://localhost', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{DEMO-secret' });
  await expect(boundedJson(request)).rejects.toBeInstanceOf(InvalidJson);
});
