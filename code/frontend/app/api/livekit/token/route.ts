import { timingSafeEqual } from 'node:crypto';
import { AccessToken, RoomAgentDispatch, RoomConfiguration } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// Per-process harness budget. Replicas also need a shared limit at ingress.
const issuance = { started: 0, count: 0 };
class RequestError extends Error {
  constructor(readonly status: number, message: string) { super(message); }
}

export async function POST(request: NextRequest) {
  try {
    assertAuthorized(request);
    const now = Date.now();
    if (now - issuance.started >= 60_000) { issuance.started = now; issuance.count = 0; }
    if (++issuance.count > 30) throw new RequestError(429, 'Too many session requests. Try again in a minute.');
    if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) {
      throw new RequestError(415, 'Send a JSON request.');
    }
    const body = parseBody(await readBody(request));
    const agentName = process.env.LIVEKIT_AGENT_NAME?.trim() || 'janmitra-agent';
    const requestedAgent = body.room_config?.agents?.[0]?.agent_name;
    if (requestedAgent && requestedAgent !== agentName) throw new RequestError(400, 'Unknown agent.');
    // Never grant caller-chosen rooms or identities.
    const token = new AccessToken(requiredEnv('LIVEKIT_API_KEY'), requiredEnv('LIVEKIT_API_SECRET'), {
      identity: `web-${crypto.randomUUID()}`,
      name: body.participant_name?.trim().split('')
        .filter((char) => char.charCodeAt(0) >= 32 && char.charCodeAt(0) !== 127)
        .join('').slice(0, 80) || 'Janmitra citizen',
      ttl: '10m', metadata: JSON.stringify({ channel: 'harness' }), attributes: { 'janmitra.channel': 'harness' },
    });
    token.addGrant({ room: `janmitra-${crypto.randomUUID()}`, roomJoin: true, canPublish: true, canPublishData: true, canSubscribe: true });
    token.roomConfig = new RoomConfiguration({ agents: [new RoomAgentDispatch({ agentName, metadata: JSON.stringify({ channel: 'harness' }) })] });
    const serverUrl = requiredEnv('LIVEKIT_URL');
    if (!['wss:', 'ws:'].includes(new URL(serverUrl).protocol)) throw new Error('Invalid LiveKit URL');
    return NextResponse.json({ server_url: serverUrl, participant_token: await token.toJwt() }, { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof RequestError) {
      return NextResponse.json({ error: error.message }, { status: error.status, headers: {
        'Cache-Control': 'no-store', ...(error.status === 429 ? { 'Retry-After': '60' } : {}),
      } });
    }
    console.error('[Janmitra] Token configuration or signing failed');
    return NextResponse.json({ error: 'Unable to start a secure voice session. Check the server configuration.' }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
}

function requiredEnv(name: 'LIVEKIT_URL' | 'LIVEKIT_API_KEY' | 'LIVEKIT_API_SECRET') {
  const value = process.env[name]?.trim();
  if (!value || value.startsWith('your_') || value.includes('your-project')) throw new Error(`${name} is not configured`);
  return value;
}

function assertAuthorized(request: NextRequest) {
  let originUrl: URL;
  try { originUrl = new URL(request.headers.get('origin') || ''); } catch {
    throw new RequestError(403, 'A same-origin browser request is required.');
  }
  const expectedOrigin = process.env.JANMITRA_HARNESS_ORIGIN?.trim()
    || `${request.nextUrl.protocol}//${request.headers.get('host') || request.nextUrl.host}`;
  if (originUrl.origin !== new URL(expectedOrigin).origin) throw new RequestError(403, 'Cross-origin request rejected.');
  const accessCode = process.env.JANMITRA_HARNESS_ACCESS_CODE?.trim();
  if (accessCode) {
    const supplied = Buffer.from(request.headers.get('x-harness-access-code') || '');
    const expected = Buffer.from(accessCode);
    if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
      throw new RequestError(401, 'Enter the harness access code to start a call.');
    }
  } else if (process.env.NODE_ENV !== 'development' || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(expectedOrigin).hostname)) {
    throw new RequestError(503, 'The harness access code is not configured on this server.');
  }
}

async function readBody(request: NextRequest): Promise<string> {
  const reader = request.body?.getReader();
  if (!reader) throw new RequestError(400, 'A JSON object is required.');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 8192) { await reader.cancel(); throw new RequestError(413, 'The session request is too large.'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks).toString('utf8');
}

type TokenRequest = { participant_name?: string; room_config?: { agents?: Array<{ agent_name?: string }> } };
function parseBody(raw: string): TokenRequest {
  let body;
  try { body = JSON.parse(raw); } catch { throw new RequestError(400, 'Invalid JSON.'); }
  if (!body || typeof body !== 'object' || Array.isArray(body) || (body.participant_name !== undefined && typeof body.participant_name !== 'string')) {
    throw new RequestError(400, 'Invalid session request.');
  }
  const config = body.room_config;
  if (config !== undefined && (!config || typeof config !== 'object' || Array.isArray(config)
    || (config.agents !== undefined && (!Array.isArray(config.agents) || config.agents.length > 1
      || config.agents.some((agent: unknown) => (!agent || typeof agent !== 'object' || Array.isArray(agent)
        || ('agent_name' in agent && typeof agent.agent_name !== 'string'))))))) {
    throw new RequestError(400, 'Invalid agent configuration.');
  }
  return body;
}
