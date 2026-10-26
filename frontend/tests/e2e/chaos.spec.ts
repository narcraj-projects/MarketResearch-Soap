import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
test.beforeEach(async ({ page, context }) => {
  test.skip(process.env.LATHER_UI_INTEGRATION !== '1' || process.env.LATHER_UI_CHAOS !== '1', 'Explicit dedicated local chaos server required.');
  const config = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
  if (new URL(config.supabase_url).origin !== 'http://127.0.0.1:57421') throw new Error('Dedicated local Auth required');
  await context.addCookies([{ name: 'lather_session', value: config.users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true, sameSite: 'Lax' }]);
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});
function ids(): Record<string, string> { return JSON.parse(fs.readFileSync(path.join(root, '.cache/chaos-ui.json'), 'utf8')); }
async function capture(page: import('@playwright/test').Page, name: string, project: string) {
  await expect(page.getByRole('heading', { name: 'Chaos switches', exact: true })).toBeVisible();
  for (const width of [768, project === 'mobile' ? 390 : 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
  const directory = path.join(root, '.cache/current-chaos-regression'); fs.mkdirSync(directory, { recursive: true });
  await page.screenshot({ path: path.join(directory, `${name}-${project}.png`), fullPage: true, animations: 'disabled' });
}
test('UI-CHAOS-GATE: disabled capability hides controls and failed creation never claims recovery', async ({ page }) => {
  await page.route('**/api/chaos/capabilities', route => route.fulfill({ json: { enabled: false, label: 'DEMO', scenarios: [] } }));
  await page.goto(`/live?run=${ids().timeout}`);
  await expect(page.getByRole('heading', { name: 'Persisted recovery evidence' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Chaos switches', exact: true })).toHaveCount(0);
  await page.unroute('**/api/chaos/capabilities'); await page.reload();
  await expect(page.getByRole('radio')).toHaveCount(9);
  await page.route('**/api/chaos/runs', route => route.fulfill({ status: 403, json: { detail: 'chaos_disabled' } }));
  await page.getByRole('button', { name: 'Queue separate DEMO scenario' }).click();
  await expect(page.locator('.chaos-controls').getByRole('alert')).toContainText('server did not confirm a test run');
  await expect(page).toHaveURL(new RegExp(ids().timeout));
});
test('UI-CHAOS-QUEUE: native keyboard selection queues a separate real DEMO run without fabricated progress', async ({ page }) => {
  await page.goto(`/live?run=${ids().timeout}`);
  const scenario = page.getByRole('radio', { name: 'Missing weight' });
  await scenario.focus(); await page.keyboard.press('Space'); await expect(scenario).toBeChecked();
  await page.getByRole('button', { name: 'Queue separate DEMO scenario' }).click();
  await expect(page).toHaveURL(/\/live\?run=[0-9a-f-]{36}$/);
  await expect(page).not.toHaveURL(new RegExp(ids().timeout));
  await expect(page.getByText('Queued for the configured local recorded worker.', { exact: false })).toBeVisible();
  await expect(page.getByTestId('recovery-retryable_failures')).toHaveText('0');
  await expect(page.getByTestId('recovery-tool_recoveries')).toHaveText('0');
  await expect(page.getByRole('heading', { name: 'No competitors persisted yet' })).toBeVisible();
  await page.reload(); await expect(page.getByTestId('recovery-worker_recoveries')).toHaveText('0');
});
test('UI-CHAOS-RECOVERY: persisted retry, schema repair and process recovery survive reload with final approval pending', async ({ page }, info) => {
  for (const [scenario, counter] of [['timeout', 'tool_recoveries'], ['malformed_json', 'model_repairs'], ['interrupted_worker', 'worker_recoveries']] as const) {
    await page.goto(`/live?run=${ids()[scenario]}`);
    await expect(page.getByTestId(`recovery-${counter}`)).toHaveText('1');
    await expect(page.getByRole('heading', { name: "The crew is waiting for you." })).toBeVisible();
    await expect(page.getByText('actual provider calls and model tokens are zero', { exact: false })).toBeVisible();
    await page.reload(); await expect(page.getByTestId(`recovery-${counter}`)).toHaveText('1');
    await capture(page, scenario, info.project.name);
  }
});
test('UI-CHAOS-LIMITS: empty evidence stops honestly; missing weight and rejected arithmetic are preserved in real report snapshots', async ({ page }, info) => {
  await page.goto(`/live?run=${ids().empty_results}`);
  await expect(page.getByRole('heading', { name: 'The run has stopped.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No competitors persisted yet' })).toBeVisible();
  await expect(page.getByTestId('recovery-tool_recoveries')).toHaveText('0');
  await capture(page, 'empty-results', info.project.name);
  for (const scenario of ['missing_weight', 'conflicting_price', 'inaccessible_page', 'reviewer_rejection']) {
    const state = await page.evaluate(async run => {
      const response = await fetch(`/api/workspace?run_id=${run}`); const value = await response.json();
      const prices = value.report.snapshot.analysis.normalized_prices.filter((row: { sku: string | null }) => row.sku === 'DEMO-A-100');
      return { status: value.run.status, quality: value.report.snapshot.coverage.genuine_support_coverage, report: value.report.version,
        exportAllowed: value.report.export_allowed, approval: value.report.approval.state,
        amounts: prices.map((row: { amount: string }) => row.amount), units: prices.map((row: { unit_price_100g: string | null }) => row.unit_price_100g),
        denied: value.report.snapshot.sources.some((source: { access_status: string }) => source.access_status === 'denied') };
    }, ids()[scenario]);
    expect(state.status).toBe('report_review'); expect(state.quality).toBeNull();
    expect(state.exportAllowed).toBe(false); expect(state.approval).toBe('pending');
    if (scenario === 'reviewer_rejection') expect(state.report).toBe(2);
    if (scenario === 'missing_weight') { expect(state.amounts).toEqual(['120']); expect(state.units).toEqual([null]); }
    if (scenario === 'conflicting_price') expect(state.amounts).toEqual(['120', '160']);
    if (scenario === 'inaccessible_page') expect(state.denied).toBe(true);
  }
});
