// Local-only browser-test launcher. Never prints configuration or credentials.
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const children = [];
let stopping = false;
const base = { ...process.env, NEXT_TELEMETRY_DISABLED: '1' };
function start(executable, args, cwd, env) {
  const child = spawn(executable, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  // Framework boot text is deliberately suppressed; error traces could include configuration.
  children.push(child);
  child.on('error', () => stop(1));
  child.on('exit', code => { if (!stopping) stop(code || 0); });
}
function stop(code = 0) { stopping = true; for (const child of children) child.kill(); process.exitCode = code; }
process.on('SIGTERM', () => stop());
process.on('SIGINT', () => stop());
try {
  if (process.env.LATHER_UI_INTEGRATION === '1') {
    const config = JSON.parse(fs.readFileSync(path.join(root, '.cache/auth-stage.json'), 'utf8'));
    if (new URL(config.supabase_url).origin !== 'http://127.0.0.1:57421' || !config.runtime_url.includes('@127.0.0.1:57422/')) throw new Error();
    const python = path.join(root, 'backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    start(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8140', '--no-access-log'], path.join(root, 'backend'), {
      ...base, LATHER_ENVIRONMENT: process.env.LATHER_UI_CHAOS === "1" ? "test" : "local", LATHER_CHAOS_ENABLED: process.env.LATHER_UI_CHAOS === "1" ? "true" : "false", LATHER_DATABASE_URL: config.runtime_url, LATHER_SUPABASE_URL: config.supabase_url, LATHER_SUPABASE_PUBLISHABLE_KEY: config.publishable_key,
    });
    base.LATHER_SUPABASE_URL = config.supabase_url;
    base.LATHER_SUPABASE_PUBLISHABLE_KEY = config.publishable_key;
  }
  // Do not pass any database credential to the frontend server.
  delete base.LATHER_DATABASE_URL;
  start(process.execPath, [path.join(root, 'frontend/node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3140'], path.join(root, 'frontend'), {
    ...base, LATHER_API_BASE_URL: 'http://127.0.0.1:8140',
  });
} catch { console.error('Local UI launcher failed. Check the local stack/configuration; no credential details emitted.'); stop(1); }
