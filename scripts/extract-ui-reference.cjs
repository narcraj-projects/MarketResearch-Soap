// Decode supplied source data without executing its scripts or fetching assets.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'docs/source-manifest.json'), 'utf8').replace(/^\uFEFF/, ''));
const html = fs.readFileSync(path.join(root, manifest.sources[2].path), 'utf8');
const block = (document, type) => JSON.parse(document.match(new RegExp('<script type="__bundler/' + type + '">([\\s\\S]*?)</script>'))[1]);
const entries = block(html, 'manifest');
const decode = (entry) => { const bytes = Buffer.from(entry.data, 'base64'); return entry.compressed ? zlib.gunzipSync(bytes) : bytes; };
const output = path.join(root, '.cache/ui-reference');
fs.mkdirSync(output, { recursive: true });
const fonts = path.join(root, 'frontend/public/fonts');
fs.mkdirSync(fonts, { recursive: true });
const css = new Set();
for (const [index, id] of block(html, 'page_order').entries()) {
  const page = decode(entries[id]).toString('utf8');
  fs.writeFileSync(path.join(output, `bundle-${index + 1}.html`), page);
  const nested = block(page, 'manifest');
  const template = block(page, 'template');
  fs.writeFileSync(path.join(output, `screen-${index + 1}.html`), template);
  for (const match of template.matchAll(/@font-face\s*\{[^}]*\}/g)) {
    let face = match[0];
    if (!face.includes('U+0000-00FF')) continue;
    const asset = face.match(/url\(["']?([0-9a-f-]{36})/);
    if (!asset || !nested[asset[1]]) continue;
    const file = asset[1] + '.woff2';
    fs.writeFileSync(path.join(fonts, file), decode(nested[asset[1]]));
    face = face.replace(asset[1], '/fonts/' + file);
    css.add(face);
  }
  const text = template.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '').replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  console.log(`SCREEN ${index + 1}: ${text}`);
}
const license = html.match(/<!--([\s\S]*?)-->/)[1];
fs.writeFileSync(path.join(fonts, 'LICENSE.txt'), license.trim() + '\n');
fs.writeFileSync(path.join(fonts, 'fonts.css'), [...css].join('\n\n') + '\n');
console.log(`Decoded five templates; extracted ${fs.readdirSync(fonts).filter(x => x.endsWith('.woff2')).length} bundled Latin fonts with source license.`);
