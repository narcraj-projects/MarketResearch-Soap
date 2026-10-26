import { test, expect } from '@playwright/test';

test('UI-SEC01: served security headers and cross-origin sign-in refusal', async ({ page, request }) => {
  const response = await page.goto('/');
  expect(response?.headers()['x-content-type-options']).toBe('nosniff');
  expect(response?.headers()['x-frame-options']).toBe('DENY');
  expect(response?.headers()['referrer-policy']).toBe('no-referrer');
  expect(response?.headers()['content-security-policy']).toContain("frame-ancestors 'none'");
  const denied = await request.post('/api/session', { headers: { Origin: 'https://evil.invalid' }, data: { email: 'DEMO@example.invalid', password: 'DEMO' } });
  expect(denied.status()).toBe(403);
  expect(denied.headers()['cache-control']).toBe('no-store');
});
