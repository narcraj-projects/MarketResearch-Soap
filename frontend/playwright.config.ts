import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const directory = path.dirname(fileURLToPath(import.meta.url));
import fs from 'node:fs';

const localBrowsers = path.resolve(directory, '../.cache/playwright');
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(localBrowsers)) process.env.PLAYWRIGHT_BROWSERS_PATH = localBrowsers;
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:3140', browserName: 'chromium', reducedMotion: 'reduce', trace: 'off', video: 'off', screenshot: 'off' },
  projects: [{ name: 'desktop', use: { viewport: { width: 1280, height: 900 } } }, { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } }],
  expect: { toHaveScreenshot: { animations: 'disabled', maxDiffPixelRatio: 0.001 } },
  webServer: { command: 'node ../scripts/serve-ui.cjs', url: 'http://127.0.0.1:3140', reuseExistingServer: false, timeout: 60000 },
});
