import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const integration = process.env.LATHER_UI_INTEGRATION === '1';
function config() {
  const cfg = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
  if (new URL(cfg.supabase_url).origin !== 'http://127.0.0.1:57421') throw new Error('Dedicated local Auth required');
  return cfg;
}
function ids() { return JSON.parse(fs.readFileSync(path.join(root, '.cache/report-ui.json'), 'utf8')); }
test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});
for (const [name, screen, fixture] of [['brief', '/', 'saved'], ['shortlist', '/shortlist', 'shortlist'], ['live', '/live', 'saved'], ['report', '/report', 'saved'], ['history', '/history', 'saved']]) {
  test(`UI-PERSIST-VIS-${name}: actual saved data and responsive screenshot`, async ({ page, context }, info) => {
    test.skip(!integration, 'Explicit dedicated local persisted fixtures required.');
    const cfg = config();
    await context.addCookies([{ name: 'lather_session', value: cfg.users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true, sameSite: 'Lax' }]);
    await page.goto(screen + (screen === '/' || screen === '/history' ? '' : `?run=${ids()[fixture]}`));
    if (name === 'brief') await expect(page.getByText(/Signed in.*saving is available/)).toBeVisible();
    else { await expect(page.locator('main[aria-busy=true]')).toHaveCount(0); await expect(page.locator('.demo-label')).toBeVisible(); }
    if (name === 'report') {
      await expect(page.getByText('Approved snapshot saved', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Intact source citations' })).toBeVisible();
      await expect(page.getByText('Missing values are not zero.', { exact: false })).toBeVisible();
      await expect(page.locator('.price-track.hatch')).not.toHaveCount(0);
      await expect(page.locator('.landscape-dot')).toHaveCount(0);
      await expect(page.locator('.opportunity')).not.toHaveCount(0);
    }
    if (name === 'live') {
      const log = page.getByLabel('Persisted run events', { exact: true });
      await expect(log).toContainText('Approved report saved.');
      await log.focus(); await expect(log).toBeFocused();
      expect(await log.evaluate(node => node.scrollHeight > node.clientHeight && node.clientHeight <= 480)).toBe(true);
    }
    await page.evaluate(() => document.fonts.ready);
    for (const width of [768, info.project.name === 'mobile' ? 390 : 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    const dir = path.join(root, '.cache/current-ui-regression'); fs.mkdirSync(dir, { recursive: true });
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: path.join(dir, `${name}-${info.project.name}.png`), fullPage: true, animations: 'disabled' });
  });
}
test('UI-PERSIST-EVIDENCE: source excerpt link date hash keyboard and reduced motion', async ({ page, context }) => {
  test.skip(!integration, 'Explicit dedicated local persisted fixtures required.');
  await context.addCookies([{ name: 'lather_session', value: config().users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true }]);
  await page.goto(`/report?run=${ids().saved}`);
  const evidence = page.getByRole('button', { name: /^Open source evidence for/ }).first();
  await evidence.click();
  const dialog = page.getByRole('dialog'); await expect(dialog).toBeVisible();
  await expect(dialog.locator('blockquote')).not.toBeEmpty();
  const url = await dialog.getByRole('link', { name: 'Open original source' }).getAttribute('href');
  expect(new URL(url!).hostname.endsWith('.invalid')).toBe(true);
  await expect(dialog.locator('time')).toBeVisible(); await expect(dialog.getByText('Content hash:', { exact: false })).toBeVisible();
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(evidence).toBeFocused();
  expect(await page.locator('.soap-badge').first().evaluate(node => getComputedStyle(node).animationName)).toBe('none');
});
test('UI-PERSIST-APPROVAL: durable decision remains blocked until worker save then downloads immutable bytes', async ({ page, context }, info) => {
  test.skip(!integration || info.project.name !== 'desktop', 'One desktop mutation of a dedicated persisted review fixture.');
  test.setTimeout(60000);
  await context.addCookies([{ name: 'lather_session', value: config().users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true }]);
  const id = ids().review; await page.goto(`/report?run=${id}`);
  await expect(page.getByRole('button', { name: 'Download HTML after approved save' })).toBeDisabled();
  await page.getByRole('button', { name: 'Approve report', exact: true }).click();
  await expect(page.getByText('Approval persisted - awaiting worker save', { exact: true })).toBeVisible();
  await page.reload(); await expect(page.getByText('Approval persisted - awaiting worker save', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve report', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Download HTML after approved save' })).toBeDisabled();
  const python = path.join(root, 'backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  execFileSync(python, ['-m', 'tools.workflow_demo', '--run-id', id], { cwd: path.join(root, 'backend'), env: { ...process.env, LANGSMITH_TRACING: 'false', LANGCHAIN_TRACING_V2: 'false' }, stdio: 'pipe', windowsHide: true, timeout: 40000 });
  await page.reload(); await expect(page.getByText('Approved snapshot saved', { exact: true })).toBeVisible();
  for (const format of ['HTML', 'CSV']) {
    const downloaded = page.waitForEvent('download'); await page.getByRole('link', { name: `Download ${format}`, exact: true }).click();
    const file = await downloaded; expect(await file.failure()).toBeNull(); expect(file.suggestedFilename()).toMatch(new RegExp(`\\.${format.toLowerCase()}$`));
    const stream = await file.createReadStream(); const chunks: Buffer[] = []; for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
    const text = Buffer.concat(chunks).toString('utf8'); expect(text).toContain('DEMO'); expect(text).toContain('not adjudicated');
  }
});
test('UI-STATE: private empty loading and retry states come from API outcomes', async ({ page }) => {
  for (const url of ['/shortlist', '/live', '/report', '/history']) {
    await page.goto(url); await expect(page.getByRole('heading', { name: 'Sign in to view your research' })).toBeVisible();
  }
  await page.route('**/api/workspace*', route => route.fulfill({ json: { schema_version: 'run-view-1.0', run: null } }));
  await page.goto('/report'); await expect(page.getByRole('heading', { name: 'No report yet' })).toBeVisible();
  await page.unroute('**/api/workspace*');
  await page.route('**/api/workspace*', route => route.fulfill({ status: 503, json: {} }));
  await page.reload(); await expect(page.locator('main').getByRole('alert')).toContainText('could not be loaded');
  await page.unroute('**/api/workspace*'); let finish: (() => Promise<void>) | undefined;
  await page.route('**/api/workspace*', route => { finish = () => route.fulfill({ json: { schema_version: 'run-view-1.0', run: null } }); });
  await page.getByRole('button', { name: 'Try again' }).click(); await expect.poll(() => !!finish).toBe(true);
  await finish!(); await expect(page.getByRole('heading', { name: 'No report yet' })).toBeVisible();
  finish = undefined; await page.reload(); await expect(page.locator('main')).toHaveAttribute('aria-busy', 'true');
  await expect.poll(() => !!finish).toBe(true);
  await finish!();
});
test('UI-KEY: skip link and brief selection use keyboard', async ({ page }) => {
  await page.goto('/'); await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter'); await expect(page.locator('main')).toBeFocused();
  const goal = page.getByRole('button', { name: 'Price my first range', exact: true }); await goal.focus(); await page.keyboard.press('Enter'); await expect(goal).toHaveAttribute('aria-pressed', 'true');
});
test('UI-SAVE-ERROR: invalid or failed saves retain input', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({ json: { authenticated: true } }));
  let saves = 0; await page.route('**/api/briefs', route => { saves++; return route.fulfill({ status: 503, json: {} }); });
  await page.goto('/'); await expect(page.getByText(/Signed in.*saving is available/)).toBeVisible();
  await page.getByRole('button', { name: /Save brief/ }).click(); expect(saves).toBe(0);
  await page.getByLabel('Target geography').fill('DEMO India'); await page.getByLabel('Target customer').fill('DEMO customer');
  await page.getByRole('button', { name: /Save brief/ }).click(); await expect(page.locator('main').getByRole('alert')).toContainText('could not be saved');
  await expect(page.getByLabel('Target geography')).toHaveValue('DEMO India');
});
