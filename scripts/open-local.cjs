// Isolated local browser: no provider keys, credentials/log output or external traffic.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const cachedBrowser = path.join(root, '.cache/playwright');
if (fs.existsSync(cachedBrowser)) process.env.PLAYWRIGHT_BROWSERS_PATH = cachedBrowser;
const { chromium } = require(path.join(root, 'frontend/node_modules/playwright'));
(async () => {
  const cfg = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
  if (cfg.supabase_url !== 'http://127.0.0.1:57421' || !cfg.runtime_url.includes('@127.0.0.1:57422/')) throw new Error();
  const live = process.argv.includes('--live');
  const ids = JSON.parse(fs.readFileSync(path.join(root, live ? '.cache/live-authorization.json' : '.cache/report-ui.json'), 'utf8'));
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, reducedMotion: 'reduce' });
  if (!live) await context.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await context.addCookies([{ name: 'lather_session', value: cfg.users[0].token, url: 'http://127.0.0.1:3140', httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:3140/' + (live ? (process.argv.includes('--report') ? 'report' : 'live') + '?run=' + ids.run_id : 'report?run=' + ids.saved));
  await page.getByRole('heading', { level: 1 }).waitFor();
  console.log(live ? 'PASS isolated local LIVE pilot browser opened.' : 'PASS isolated local DEMO browser opened.');
  await new Promise(resolve => browser.on('disconnected', resolve));
})().catch(() => { console.error('Local browser failed; private details suppressed. Check the local servers and session.'); process.exitCode = 1; });
