// Read bundle data only. Never execute scripts from the supplied reference.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'docs/source-manifest.json'), 'utf8').replace(/^\uFEFF/, ''));
const html = fs.readFileSync(path.join(root, manifest.sources[2].path), 'utf8');
function block(document, type) {
  const match = document.match(new RegExp('<script type="__bundler/' + type + '">([\\s\\S]*?)</script>'));
  assert.ok(match, 'Missing bundle block: ' + type);
  return JSON.parse(match[1]);
}
const assets = block(html, 'manifest');
const order = block(html, 'page_order');
assert.equal(order.length, 5, 'Expected five reference screens');
assert.equal(new Set(order).size, 5, 'Duplicate reference screen');
for (const id of order) {
  const entry = assets[id];
  assert.equal(entry.mime, 'text/html');
  const bytes = Buffer.from(entry.data, 'base64');
  const page = (entry.compressed ? zlib.gunzipSync(bytes) : bytes).toString('utf8');
  const template = block(page, 'template');
  assert.equal(typeof template, 'string');
  assert.ok(template.includes('Lather Lens'), 'Missing product name');
  const title = template.match(/<title>([^<]+)<\/title>/i);
  assert.ok(title, 'Missing screen title');
  console.log('PASS decoded reference: ' + title[1]);
}
console.log('Five UI templates readable. Visual fidelity has not been tested.');
