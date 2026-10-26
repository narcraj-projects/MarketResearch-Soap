// Per-process safety valves. Shared edge limits remain required before hosting.
export const BODY_LIMIT = 65536;
export class InputLimit extends Error {}
export class InvalidJson extends Error {}
export async function boundedJson(request: Request): Promise<unknown> {
  const length = request.headers.get('content-length');
  if (length && (!/^\d+$/.test(length) || Number(length) > BODY_LIMIT)) throw new InputLimit();
  if (request.headers.get('content-encoding') && request.headers.get('content-encoding') !== 'identity') throw new InputLimit();
  if (request.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'application/json') throw new InputLimit();
  const reader = request.body?.getReader();
  if (!reader) throw new InputLimit();
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > BODY_LIMIT) throw new InputLimit();
      chunks.push(chunk.value);
    }
  } finally { await reader.cancel(); reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
  catch { throw new InvalidJson(); }
}
export class LoginLimiter {
  private began = 0; private count = 0;
  constructor(private clock = Date.now, private limit = 30) {}
  allow(): boolean {
    const now = this.clock();
    if (now - this.began >= 60000) { this.began = now; this.count = 0; }
    return ++this.count <= this.limit;
  }
}
export const loginLimiter = new LoginLimiter();
