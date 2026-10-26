const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const { chromium } = createRequire(path.join(root, 'frontend/package.json'))('@playwright/test');
(async () => {
  const browser = await chromium.launch();
  try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1240 }, reducedMotion: 'reduce' });
  await page.route(/^https?:/, route => route.abort());
  const folder = path.join(root, 'docs/ui-screenshots/reference');
  fs.mkdirSync(folder, { recursive: true });
  for (const [index, height] of [1240, 1320, 1300, 2600, 1240].entries()) {
    await page.setViewportSize({ width: 1280, height });
    await page.goto(pathToFileURL(path.join(root, `.cache/ui-reference/bundle-${index + 1}.html`)).href);
    await page.locator('h1').waitFor({ timeout: 30000 });
    await page.evaluate(() => document.fonts.ready);
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
    await page.screenshot({ path: path.join(folder, `${index + 1}.png`), fullPage: true, animations: 'disabled' });
    console.log(`Captured original screen ${index + 1}: ${await page.locator('h1').innerText()}`);
  }
  } finally { await browser.close(); }
})().catch(() => { console.error('Reference capture failed; no remote requests were permitted.'); process.exitCode = 1; });
