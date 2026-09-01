import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
  type VideoGrant,
} from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

type TokenRequest = {
  room_name?: string;
  participant_identity?: string;
  participant_name?: string;
  room_config?: { agents?: Array<{ agent_name?: string }> };
};

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    assertSameOrigin(request);
    const body = (await request.json()) as TokenRequest;
    const agentName = process.env.LIVEKIT_AGENT_NAME?.trim() || 'janmitra-agent';
    const requestedAgent = body.room_config?.agents?.[0]?.agent_name;
    if (requestedAgent && requestedAgent !== agentName) {
      return NextResponse.json({ error: 'Unknown agent.' }, { status: 400 });
    }

    const roomName = safeIdentifier(body.room_name) ?? `janmitra-${crypto.randomUUID()}`;
    const identity = safeIdentifier(body.participant_identity) ?? `web-${crypto.randomUUID()}`;
    const token = new AccessToken(
      requiredEnv('LIVEKIT_API_KEY'),
      requiredEnv('LIVEKIT_API_SECRET'),
      {
        identity,
        name: safeName(body.participant_name) ?? 'Janmitra citizen',
        ttl: '10m',
        metadata: JSON.stringify({ channel: 'harness' }),
        attributes: { 'janmitra.channel': 'harness' },
      },
    );
    const grant: VideoGrant = {
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canPublishData: true,
      canSubscribe: true,
    };
    token.addGrant(grant);
    token.roomConfig = new RoomConfiguration({
      agents: [
        new RoomAgentDispatch({
          agentName,
          metadata: JSON.stringify({ channel: 'harness' }),
        }),
      ],
    });

    return NextResponse.json(
      {
        server_url: requiredEnv('LIVEKIT_URL'),
        participant_token: await token.toJwt(),
      },
      { headers: { 'Cache-Control': 'no-store' } },
    );
  } catch (error) {
    console.error('[Janmitra] Token generation failed', error);
    return NextResponse.json(
      { error: 'Unable to start a secure voice session.' },
      { status: 500 },
    );
  }
}

function requiredEnv(name: 'LIVEKIT_URL' | 'LIVEKIT_API_KEY' | 'LIVEKIT_API_SECRET') {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not configured`);
  return value;
}

function safeIdentifier(value?: string) {
  const sanitized = value?.trim().replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 128);
  return sanitized || undefined;
}

function safeName(value?: string) {
  const sanitized = value?.trim().replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 80);
  return sanitized || undefined;
}

function assertSameOrigin(request: NextRequest) {
  const origin = request.headers.get('origin');
  const host = request.headers.get('host');
  if (origin && host && new URL(origin).host !== host) {
    throw new Error('Cross-origin request rejected');
  }
}
