'use client';

import {
  RoomAudioRenderer,
  SessionProvider,
  useAgent,
  useSession,
} from '@livekit/components-react';
import { TokenSource } from 'livekit-client';
import { CircleAlert, Mic, MicOff, Phone, PhoneOff, Radio, ShieldCheck } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';

const AGENT_NAME = process.env.NEXT_PUBLIC_LIVEKIT_AGENT_NAME || 'janmitra-agent';

export default function VoiceCall() {
  const tokenSource = useMemo(() => TokenSource.endpoint('/api/livekit/token'), []);
  const reactId = useId();
  const identity = `web-${reactId.replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const session = useSession(tokenSource, {
    agentName: AGENT_NAME,
    agentMetadata: JSON.stringify({ channel: 'harness' }),
    participantIdentity: identity,
    participantName: 'Janmitra citizen',
  });
  const agent = useAgent(session);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const active = session.isConnected;

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  async function start() {
    setError(null);
    setSeconds(0);
    setMuted(false);
    try {
      await session.start({ tracks: { microphone: { enabled: true } } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start the call.');
    }
  }

  async function stop() {
    setError(null);
    try {
      await session.end();
    } finally {
      setSeconds(0);
      setMuted(false);
    }
  }

  async function toggleMute() {
    const next = !muted;
    try {
      await session.room.localParticipant.setMicrophoneEnabled(!next);
      setMuted(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not update the microphone.');
    }
  }

  const status = !active
    ? session.connectionState === 'connecting'
      ? 'Connecting'
      : 'Ready'
    : agent.state === 'speaking'
      ? 'Speaking'
      : agent.state === 'thinking'
        ? 'Thinking'
        : agent.state === 'listening'
          ? 'Listening'
          : 'Connected';
  const elapsed = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer />
      <main className="workspace">
        <header className="topbar">
          <div className="brand">
            <span className="brand-mark">J</span>
            <span>Janmitra</span>
          </div>
          <span className="environment"><Radio size={15} /> Voice harness</span>
        </header>

        <section className="call-layout">
          <aside className="context-panel">
            <p className="eyebrow">Current session</p>
            <h1>Government scheme guidance</h1>
            <dl>
              <div><dt>Channel</dt><dd>Browser harness</dd></div>
              <div><dt>Language</dt><dd>Detected during call</dd></div>
              <div><dt>Privacy</dt><dd>Minimal details only</dd></div>
            </dl>
            <p className="trust-note"><ShieldCheck size={18} /> Guidance is grounded in reviewed records.</p>
          </aside>

          <section className="call-stage" aria-live="polite">
            <div className={`voice-signal ${active ? 'is-active' : ''}`} aria-hidden="true">
              <span /><span /><span /><span /><span />
            </div>
            <p className="status">{status}</p>
            <p className="timer">{active ? elapsed : '00:00'}</p>
            <h2>Janmitra AI</h2>
            <p className="subtitle">Public information assistant</p>

            {error && <p className="error" role="alert"><CircleAlert size={18} />{error}</p>}

            <div className="controls">
              {active && (
                <button
                  className={`icon-button ${muted ? 'is-muted' : ''}`}
                  onClick={toggleMute}
                  aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
                  title={muted ? 'Unmute microphone' : 'Mute microphone'}
                >
                  {muted ? <MicOff /> : <Mic />}
                </button>
              )}
              <button
                className={`call-button ${active ? 'end' : 'start'}`}
                onClick={active ? stop : start}
                disabled={!active && session.connectionState === 'connecting'}
                aria-label={active ? 'End call' : 'Start call'}
              >
                {active ? <PhoneOff /> : <Phone />}
                <span>{active ? 'End call' : 'Start call'}</span>
              </button>
            </div>
          </section>

          <aside className="status-panel">
            <p className="eyebrow">Connection</p>
            <div className="connection-row"><span className={active ? 'dot online' : 'dot'} />{status}</div>
            <div className="divider" />
            <p className="small-copy">Official decisions remain with the responsible department.</p>
          </aside>
        </section>
      </main>
    </SessionProvider>
  );
}
