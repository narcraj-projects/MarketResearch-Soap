import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
test.beforeEach(async ({ page, context }) => {
  test.skip(process.env.LATHER_UI_INTEGRATION !== '1', 'Dedicated local history DEMO fixtures required.');
  const config = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
  if (new URL(config.supabase_url).origin !== 'http://127.0.0.1:57421') throw new Error('Dedicated local Auth required');
  await context.addCookies([{ name: 'lather_session', value: config.users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true, sameSite: 'Lax' }]);
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});
function ids() { return JSON.parse(fs.readFileSync(path.join(root, '.cache/history-ui.json'), 'utf8')); }
async function capture(page: import('@playwright/test').Page, name: string, project: string) {
  for (const width of [768, project === 'mobile' ? 390 : 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
  const dir = path.join(root, '.cache/current-history-regression'); fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}-${project}.png`), fullPage: true, animations: 'disabled' });
}
test('UI-HISTORY-DIFF: selected immutable versions show supported price/new/gone and dated source evidence', async ({ page }, info) => {
  const fixture = ids();
  await page.goto(`/history?before=${fixture.before}&after=${fixture.after}&before_version=2&after_version=1`);
  await expect(page.getByRole('button', { name: 'Compare saved reports' })).toBeEnabled();
  await expect(page.getByTestId('history-count-changed')).toHaveText('--');
  await page.getByRole('button', { name: 'Compare saved reports' }).click();
  await expect(page.getByTestId('history-count-changed')).toHaveText('1');
  await expect(page.getByTestId('history-count-gone')).toHaveText('1');
  expect(Number(await page.getByTestId('history-count-new').innerText())).toBeGreaterThan(0);
  const price = page.getByTestId('history-diff-changed').filter({ has: page.getByRole('heading', { name: /DEMO-A-100 - price/ }) });
  await expect(price).toContainText('120 INR'); await expect(price).toContainText('140 INR');
  const source = price.getByRole('button', { name: /^Evidence/ }).last(); await source.click();
  await expect(page.getByRole('dialog').locator('blockquote')).not.toBeEmpty();
  await expect(page.getByRole('dialog').locator('time')).toBeVisible();
  await page.keyboard.press('Escape'); await expect(source).toBeFocused();
  await capture(page, 'supported-diff', info.project.name);
  const hash = await page.evaluate(async run => { const response = await fetch(`/api/runs/${run}/versions`); const data = await response.json(); return data.entries.find((entry: { version: number }) => entry.version === 1).content_hash; }, fixture.before);
  await page.getByText('2 immutable report versions', { exact: true }).click();
  await page.getByRole('link', { name: 'Read v1 - unavailable', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`run=${fixture.before}&version=1$`));
  await expect(page.locator('.snapshot-status code')).toHaveText(hash);
  await expect(page.getByRole('button', { name: 'Approve report', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Download HTML after approved save' })).toBeDisabled();
  await page.reload(); await expect(page.getByRole('button', { name: 'Download HTML after approved save' })).toBeDisabled();
});
test('UI-HISTORY-GAP: unavailable website has unknown counts and never a discontinued inference', async ({ page }, info) => {
  const fixture = ids();
  await page.goto(`/history?before=${fixture.before}&after=${fixture.unavailable}&before_version=2&after_version=1`);
  await page.getByRole('button', { name: 'Compare saved reports' }).click();
  await expect(page.getByTestId('history-count-gone')).toHaveText('0');
  const price = page.getByTestId('history-diff-unknown').filter({ has: page.getByRole('heading', { name: /DEMO-A-100 - price/ }) });
  await expect(price).toContainText('120 INR'); await expect(price).toContainText('Unavailable in this report');
  await expect(price).toContainText('retrieval gap not discontinued');
  await capture(page, 'unavailable-website', info.project.name);
  await price.getByRole('button', { name: /unavailable$/ }).click();
  await expect(page.getByRole('dialog')).toContainText('does not establish discontinuation');
  await page.keyboard.press('Escape');
  const later = page.getByRole('combobox', { name: 'Later run', exact: true });
  while (await later.locator(`option[value="${fixture.before}"]`).count() === 0) {
    const previous = await page.locator('.timeline>li').count();
    await page.getByRole('button', { name: 'Load more saved runs' }).click();
    await expect.poll(() => page.locator('.timeline>li').count()).toBeGreaterThan(previous);
  }
  await later.selectOption(fixture.before);
  await expect(page.getByTestId('history-count-gone')).toHaveText('--');
  await page.getByRole('button', { name: 'Compare saved reports' }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('two different runs');
  await expect(page.getByTestId('history-count-changed')).toHaveText('--');
});
