import { NextRequest } from 'next/server';
import { TokenVerifier } from 'livekit-server-sdk';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let post: typeof import('../app/api/livekit/token/route').POST;

beforeEach(async () => {
  vi.resetModules();
  vi.stubEnv('NODE_ENV', 'production');
  vi.stubEnv('JANMITRA_HARNESS_ACCESS_CODE', 'test-access');
  vi.stubEnv('LIVEKIT_API_KEY', 'test-key');
  vi.stubEnv('LIVEKIT_API_SECRET', 'test-secret-that-is-long-enough-to-sign');
  vi.stubEnv('LIVEKIT_URL', 'wss://example.livekit.cloud');
  vi.stubEnv('LIVEKIT_AGENT_NAME', 'janmitra-agent');
  vi.stubEnv('JANMITRA_HARNESS_ORIGIN', '');
  post = (await import('../app/api/livekit/token/route')).POST;
});
afterEach(() => { vi.unstubAllEnvs(); vi.restoreAllMocks(); });

function request(body: unknown = {}, extra: Record<string, string> = {}) {
  return new NextRequest('https://harness.example/api/livekit/token', {
    method: 'POST', headers: {
      origin: 'https://harness.example', 'content-type': 'application/json',
      'x-harness-access-code': 'test-access', ...extra,
    }, body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

describe('voice session tokens', () => {
  it('uses the browser host when Next internally resolves localhost', async () => {
    vi.stubEnv('NODE_ENV', 'development');
    vi.stubEnv('JANMITRA_HARNESS_ACCESS_CODE', '');
    const req = new NextRequest('http://localhost:3000/api/livekit/token', {
      method: 'POST', headers: { origin: 'http://127.0.0.1:3000', host: '127.0.0.1:3000',
        'content-type': 'application/json' }, body: '{}',
    });
    expect((await post(req)).status).toBe(200);
  });

  it('accepts an explicitly configured public origin behind an HTTPS proxy', async () => {
    vi.stubEnv('JANMITRA_HARNESS_ORIGIN', 'https://public.example');
    expect((await post(request({}, { origin: 'https://public.example' }))).status).toBe(200);
    expect((await post(request())).status).toBe(403);
  });

  it('signs isolated rooms and identities without leaking credentials', async () => {
    const response = await post(request({ room_name: 'victim-room', participant_identity: 'victim' }));
    expect(response.status).toBe(200);
    expect(response.headers.get('cache-control')).toBe('no-store');
    const body = await response.json();
    const verifier = new TokenVerifier('test-key', 'test-secret-that-is-long-enough-to-sign');
    const payload = await verifier.verify(body.participant_token);
    expect(payload.sub).toMatch(/^web-/);
    expect(payload.sub).not.toBe('victim');
    expect((payload.video as { room: string }).room).toMatch(/^janmitra-/);
    expect((payload.video as { room: string }).room).not.toBe('victim-room');
    expect(Number(payload.exp) - Number(payload.nbf)).toBe(600);
    expect(Object.keys(body).sort()).toEqual(['participant_token', 'server_url']);
    const second = await (await post(request())).json();
    const other = await verifier.verify(second.participant_token);
    expect(other.sub).not.toBe(payload.sub);
  });

  it.each(['', 'https://attacker.example', 'http://harness.example', 'not-a-url'])(
    'rejects a missing or foreign origin: %s', async (origin) => {
      expect((await post(request({}, { origin }))).status).toBe(403);
    },
  );

  it('requires hosted access authorization', async () => {
    expect((await post(request({}, { 'x-harness-access-code': '' }))).status).toBe(401);
    vi.stubEnv('JANMITRA_HARNESS_ACCESS_CODE', '');
    expect((await post(request())).status).toBe(503);
  });

  it.each([null, [], '{', { participant_name: 42 }, { room_config: { agents: [null] } },
    { room_config: { agents: [{ agent_name: 'other-agent' }] } }])(
    'rejects malformed input: %j', async (body) => {
      expect((await post(request(body))).status).toBe(400);
    },
  );

  it('limits body size and content type', async () => {
    expect((await post(request({ participant_name: 'a'.repeat(9000) }))).status).toBe(413);
    expect((await post(request({}, { 'content-type': 'text/plain' }))).status).toBe(415);
  });

  it('limits repeated token issuance', async () => {
    for (let n = 0; n < 30; n++) expect((await post(request())).status).toBe(200);
    const response = await post(request());
    expect(response.status).toBe(429);
    expect(response.headers.get('retry-after')).toBe('60');
  });

  it('returns a recoverable error for missing server credentials', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.stubEnv('LIVEKIT_API_SECRET', '');
    expect((await post(request())).status).toBe(503);
  });
});
