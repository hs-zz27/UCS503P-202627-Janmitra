'use client';

import {
  RoomAudioRenderer,
  SessionProvider,
  useAgent,
  useSession,
  useSessionMessages,
} from '@livekit/components-react';
import { ParticipantKind, RoomEvent, TokenSource, type RemoteParticipant } from 'livekit-client';
import { CircleAlert, Mic, MicOff, Phone, PhoneOff, Radio, ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseVoiceEvent } from '../lib/voice-events';

const AGENT_NAME = process.env.NEXT_PUBLIC_LIVEKIT_AGENT_NAME || 'janmitra-agent';

export default function VoiceCall() {
  const [accessCode, setAccessCode] = useState('');
  const tokenSource = useMemo(() => TokenSource.endpoint('/api/livekit/token', {
    headers: accessCode ? { 'X-Harness-Access-Code': accessCode } : {},
  }), [accessCode]);
  const session = useSession(tokenSource, {
    agentName: AGENT_NAME,
    agentMetadata: JSON.stringify({ channel: 'harness' }),
    participantName: 'Janmitra citizen',
  });
  const agent = useAgent(session);
  const { messages } = useSessionMessages(session);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [callStartedAt, setCallStartedAt] = useState(0);
  const [notice, setNotice] = useState('Start a call, then speak when Janmitra is listening.');
  const active = session.isConnected;

  useEffect(() => {
    const onData = (payload: Uint8Array, participant?: RemoteParticipant,
      _kind?: unknown, topic?: string) => {
      if (topic !== 'janmitra.voice' || participant?.kind !== ParticipantKind.AGENT) return;
      const event = parseVoiceEvent(payload);
      if (!event) return;
      if (event.type === 'error') setError(event.message || 'The voice service is unavailable. End the call and try again.');
      else if (event.type === 'ready') {
        setError(null);
        setNotice('Speak naturally. You can interrupt Janmitra while it is speaking.');
      }
    };
    session.room.on(RoomEvent.DataReceived, onData);
    return () => { session.room.off(RoomEvent.DataReceived, onData); };
  }, [session.room]);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  async function start() {
    setError(null);
    setSeconds(0);
    setMuted(false);
    setCallStartedAt(Date.now());
    setNotice('Connecting to Janmitra. Please wait for Listening.');
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
      setNotice('Call ended. Start a new call whenever you are ready.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not end the call.');
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
          : agent.state === 'failed'
            ? 'Assistant unavailable'
            : 'Preparing assistant';
  const displayError = error || (active && agent.state === 'failed'
    ? 'Janmitra could not connect. End the call and try again.' : null);
  const transcript = messages.filter((message) => message.timestamp >= callStartedAt
    && (message.type === 'userTranscript' || message.type === 'agentTranscript')).slice(-8);
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
          <span className="environment"><Radio size={15} /> Browser voice</span>
        </header>

        <section className="call-layout">
          <aside className="context-panel">
            <p className="eyebrow">Current session</p>
            <h1>Find support for your next step</h1>
            <dl>
              <div><dt>Channel</dt><dd>Browser microphone</dd></div>
              <div><dt>Language</dt><dd>Detected during call</dd></div>
              <div><dt>Privacy</dt><dd>Calls are transcribed for support</dd></div>
            </dl>
            <p className="trust-note"><ShieldCheck size={18} /> Reviewed guidance comes first. General answers are labelled unverified.</p>
            <label className="access-code">
              Access code (if required)
              <input type="password" value={accessCode} autoComplete="off"
                disabled={active || session.connectionState === 'connecting'}
                onChange={(event) => setAccessCode(event.target.value)} />
            </label>
          </aside>

          <section className="call-stage" aria-live="polite">
            <div className={`voice-signal ${active ? 'is-active' : ''}`} aria-hidden="true">
              <span /><span /><span /><span /><span />
            </div>
            <p className="status">{status}</p>
            <p className="timer">{active ? elapsed : '00:00'}</p>
            <h2>Janmitra AI</h2>
            <p className="subtitle">Public information assistant</p>

            <p className="call-notice">{notice}</p>
            {displayError && <p className="error" role="alert"><CircleAlert size={18} />{displayError}</p>}

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
            <section className="transcript" aria-label="Live conversation">
              <h3>Conversation</h3>
              {transcript.length === 0
                ? <p className="transcript-empty">Your words and Janmitra’s replies appear here during the call.</p>
                : <ol>{transcript.map((message) => (
                  <li key={message.id} className={message.type === 'userTranscript' ? 'from-user' : 'from-agent'}>
                    <strong>{message.type === 'userTranscript' ? 'You' : 'Janmitra'}</strong>
                    <p>{message.message}</p>
                  </li>
                ))}</ol>}
            </section>
          </section>

          <aside className="status-panel">
            <p className="eyebrow">Connection</p>
            <div className="connection-row"><span className={active ? 'dot online' : 'dot'} />{status}</div>
            <div className="divider" />
            <p className="small-copy">Official decisions remain with the responsible department.</p>
            <p className="small-copy">Ask about crop insurance, pensions, housing, or support for a small business.</p>
          </aside>
        </section>
      </main>
    </SessionProvider>
  );
}
