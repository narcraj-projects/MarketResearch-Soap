import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const directory = path.dirname(fileURLToPath(import.meta.url));
import crypto from 'node:crypto';

test('UI-API: real API sign-in, owner save, idempotency and persisted reload', async ({ page, request }) => {
  test.skip(process.env.LATHER_UI_INTEGRATION !== '1', 'Requires the explicit dedicated local Supabase stack; never a paid/cloud API.');
  const config = JSON.parse(fs.readFileSync(path.resolve(directory, '../../../.cache/auth-stage.json'), 'utf8'));
  if (new URL(config.supabase_url).origin !== 'http://127.0.0.1:57421') throw new Error('Dedicated local Auth required');
  const email = `demo-ui-${crypto.randomUUID()}@example.invalid`;
  const password = crypto.randomBytes(30).toString('base64url');
  const signup = await request.post(config.supabase_url + '/auth/v1/signup', { headers: { apikey: config.publishable_key }, data: { email, password } });
  // Never include response bodies, tokens or credentials in assertions/artifacts.
  expect(signup.status()).toBe(200);
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in to account' }).click();
  await expect(page.getByText('Signed in · saving is available')).toBeVisible();
  expect(await page.evaluate(() => document.cookie.includes('lather_session'))).toBe(false);
  await page.getByLabel('Target geography').fill('DEMO India online');
  await page.getByLabel('Target customer').fill('DEMO sensitive-skin shoppers');
  await page.getByLabel('What do you want to decide?').fill('DEMO persistence verification');
  await page.getByRole('button', { name: /Mid-premium/ }).click();
  await page.getByText('Compare your bar (optional)', { exact: true }).click();
  await page.getByLabel('Your bar price').fill('125');
  await page.getByLabel('Total bar weight').fill('100');
  await page.getByRole('button', { name: /Save brief/ }).click();
  const receipt = page.getByTestId('saved-brief-id');
  await expect(receipt).toBeVisible();
  const id = await receipt.innerText();
  await page.getByRole('button', { name: 'Reload saved brief', exact: true }).click();
  await expect(page.getByText('Saved geography: DEMO India online · segment: Mid-premium')).toBeVisible();
  await page.getByRole('button', { name: 'Queue recorded research', exact: true }).click();
  await expect(page).toHaveURL(/\/live\?run=[0-9a-f-]{36}$/);
  await expect(page.getByText('Queued for the configured local recorded worker.', { exact: false })).toBeVisible();
  const queued = await page.evaluate(async () => {
    const id = new URL(location.href).searchParams.get('run');
    const response = await fetch(`/api/workspace?run_id=${id}`); const body = await response.json();
    return { status: response.status, state: body.run.status, calls: body.usage.calls, maxCost: body.run.budget.max_cost_usd, demo: body.label };
  });
  expect(queued).toEqual({ status: 200, state: 'queued', calls: 0, maxCost: '0', demo: 'DEMO' });
  await page.goto('/');
  await page.reload();
  const record = await page.evaluate(async briefId => {
    const response = await fetch(`/api/briefs/${briefId}`);
    const body = await response.json();
    return { status: response.status, geography: body.geography, segment: body.preferences?.price_segment, price: body.preferences?.own_price, weight: body.preferences?.own_weight_g };
  }, id);
  expect(record).toEqual({ status: 200, geography: 'DEMO India online', segment: 'Mid-premium', price: '125', weight: '100' });
  // Retry the exact submission key/payload through the BFF and prove it reuses one record.
  const replay = await page.evaluate(async () => {
    const payload = { category: 'DEMO soap', geography: 'DEMO India', customer: 'DEMO buyer', objective: 'DEMO idempotency' };
    const key = crypto.randomUUID();
    const send = async () => { const r = await fetch('/api/briefs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify(payload) }); const b = await r.json(); return { status: r.status, id: b.id }; };
    return [await send(), await send()];
  });
  expect(replay[0].status).toBe(201); expect(replay[1]).toEqual(replay[0]);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByText('Sign in to save to your account', { exact: true })).toBeVisible();
  const after = await page.evaluate(async briefId => (await fetch(`/api/briefs/${briefId}`)).status, id);
  expect(after).toBe(401);
});
