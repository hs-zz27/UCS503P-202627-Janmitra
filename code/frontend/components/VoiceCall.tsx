'use client';

import {
  RoomAudioRenderer,
  SessionProvider,
  useAgent,
  useSession,
  useSessionMessages,
} from '@livekit/components-react';
import { ParticipantKind, RoomEvent, TokenSource, type RemoteParticipant } from 'livekit-client';
import {
  Captions,
  CircleAlert,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  ShieldCheck,
  Volume1,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { parseVoiceEvent } from '../lib/voice-events';

const AGENT_NAME = process.env.NEXT_PUBLIC_LIVEKIT_AGENT_NAME || 'janmitra-agent';
const TOPICS = ['Crop insurance', 'Old-age pensions', 'Housing schemes', 'Small-business support'];
const MAX_VOLUME = 10;

type Screen = 'idle' | 'connecting' | 'active' | 'ended';

function formatTime(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

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
  const [speaker, setSpeaker] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [volume, setVolume] = useState(7);
  const [seconds, setSeconds] = useState(0);
  const [ended, setEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callStartedAt, setCallStartedAt] = useState(0);
  const active = session.isConnected;
  const connecting = !active && session.connectionState === 'connecting';

  useEffect(() => {
    const onData = (payload: Uint8Array, participant?: RemoteParticipant,
      _kind?: unknown, topic?: string) => {
      if (topic !== 'janmitra.voice' || participant?.kind !== ParticipantKind.AGENT) return;
      const event = parseVoiceEvent(payload);
      if (!event) return;
      if (event.type === 'error') setError(event.message || 'The voice service is unavailable. End the call and try again.');
      else if (event.type === 'ready') setError(null);
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
    setEnded(false);
    setSeconds(0);
    setMuted(false);
    setCallStartedAt(Date.now());
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
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not end the call.');
    } finally {
      setEnded(true);
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

  const screen: Screen = active ? 'active' : connecting ? 'connecting' : ended ? 'ended' : 'idle';
  const status = muted
    ? 'Muted'
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
  const speaking = active && agent.state === 'speaking';

  const transcriptList = transcript.length === 0
    ? <p className="transcript-empty">Your words and Janmitra’s replies appear here during the call.</p>
    : (
      <ol className="transcript-list">
        {transcript.map((message) => (
          <li key={message.id} className={message.type === 'userTranscript' ? 'from-user' : 'from-agent'}>
            <strong>{message.type === 'userTranscript' ? 'You' : 'Janmitra'}</strong>
            <p>{message.message}</p>
          </li>
        ))}
      </ol>
    );

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer volume={speaker ? volume / MAX_VOLUME : 0} />
      <main className="call-app">
        <header className="call-topbar">
          <span className="brand"><span className="brand-mark">J</span>Janmitra</span>
          <span className="secure"><ShieldCheck size={16} aria-hidden="true" />Secure browser call</span>
        </header>

        <div className="call-body">
          <aside className="side-panel side-help" aria-label="What you can ask">
            <p className="eyebrow">You can ask about</p>
            <ul className="topic-list">
              {TOPICS.map((topic) => <li key={topic}>{topic}</li>)}
            </ul>
            <p className="side-note">
              Speak in your own language; Janmitra detects it during the call. Reviewed guidance
              comes first; general answers are labelled unverified.
            </p>
          </aside>

          <section className="phone" aria-live="polite" aria-label="Janmitra call">
            <div className="phone-top">
              <span className="brand small"><span className="brand-mark">J</span>Janmitra</span>
              <span className="secure"><ShieldCheck size={15} aria-hidden="true" />Secure call</span>
            </div>

            <div className={`avatar-rings ${screen === 'active' || screen === 'connecting' ? 'is-live' : ''} ${speaking ? 'is-speaking' : ''}`} aria-hidden="true">
              <div className="ring"><div className="avatar">J</div></div>
            </div>
            <h1 className="caller-name">Janmitra AI</h1>

            {screen === 'idle' && (
              <>
                <p className="caller-sub">Public information helpline</p>
                <div className="phone-fill" />
                <p className="phone-hint">
                  Ask about crop insurance, pensions, housing, or support for a small business.
                </p>
                {displayError && <p className="call-error" role="alert"><CircleAlert size={16} aria-hidden="true" />{displayError}</p>}
                <button type="button" className="round-call start" onClick={start} aria-label="Call Janmitra">
                  <Phone size={30} aria-hidden="true" />
                </button>
                <p className="round-label">Call</p>
                <label className="access-code">
                  Access code (if required)
                  <input type="password" value={accessCode} autoComplete="off"
                    onChange={(event) => setAccessCode(event.target.value)} />
                </label>
              </>
            )}

            {screen === 'connecting' && (
              <>
                <p className="caller-sub">Calling…</p>
                <p className="caller-sub small">Allow microphone access when asked</p>
                <div className="phone-fill" />
                <button type="button" className="round-call end" disabled aria-label="Connecting">
                  <PhoneOff size={30} aria-hidden="true" />
                </button>
                <p className="round-label">Connecting</p>
              </>
            )}

            {screen === 'active' && (
              <>
                <p className="caller-sub status-line">
                  <span className={`status-dot ${muted ? 'is-muted' : ''}`} />
                  {status} · {formatTime(seconds)}
                </p>

                <div className="phone-fill middle">
                  {displayError && <p className="call-error" role="alert"><CircleAlert size={16} aria-hidden="true" />{displayError}</p>}
                  {captions && <div className="captions-card">{transcriptList}</div>}
                </div>

                <div className="control-grid">
                  <div className="control">
                    <button type="button" className={`round ${muted ? 'is-on' : ''}`} onClick={toggleMute}
                      aria-pressed={muted} aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}>
                      {muted ? <MicOff size={24} aria-hidden="true" /> : <Mic size={24} aria-hidden="true" />}
                    </button>
                    <span>{muted ? 'Unmute' : 'Mute'}</span>
                  </div>
                  <div className="control">
                    <button type="button" className={`round ${speaker ? 'is-on' : ''}`} onClick={() => setSpeaker(!speaker)}
                      aria-pressed={speaker} aria-label="Speaker">
                      {speaker ? <Volume2 size={24} aria-hidden="true" /> : <VolumeX size={24} aria-hidden="true" />}
                    </button>
                    <span>Speaker</span>
                  </div>
                  <div className="control">
                    <button type="button" className={`round ${captions ? 'is-on' : ''}`} onClick={() => setCaptions(!captions)}
                      aria-pressed={captions} aria-label="Captions">
                      <Captions size={24} aria-hidden="true" />
                    </button>
                    <span>Captions</span>
                  </div>
                  <div className="control">
                    <button type="button" className="round" onClick={() => setVolume(Math.max(0, volume - 1))}
                      disabled={volume === 0} aria-label="Volume down">
                      <Volume1 size={24} aria-hidden="true" />
                    </button>
                    <span>Vol −</span>
                  </div>
                  <div className="control volume-meter">
                    <div className="volume-bar" role="meter" aria-label="Volume" aria-valuemin={0}
                      aria-valuemax={MAX_VOLUME} aria-valuenow={volume}>
                      <div style={{ width: `${(volume / MAX_VOLUME) * 100}%` }} />
                    </div>
                    <span>Volume {volume}</span>
                  </div>
                  <div className="control">
                    <button type="button" className="round" onClick={() => setVolume(Math.min(MAX_VOLUME, volume + 1))}
                      disabled={volume === MAX_VOLUME} aria-label="Volume up">
                      <Volume2 size={24} aria-hidden="true" />
                    </button>
                    <span>Vol +</span>
                  </div>
                </div>

                <button type="button" className="round-call end" onClick={stop} aria-label="End call">
                  <PhoneOff size={30} aria-hidden="true" />
                </button>
              </>
            )}

            {screen === 'ended' && (
              <>
                <p className="caller-sub">Call ended · {formatTime(seconds)}</p>
                <p className="phone-hint">Official decisions remain with the responsible department.</p>
                <div className="phone-fill" />
                {displayError && <p className="call-error" role="alert"><CircleAlert size={16} aria-hidden="true" />{displayError}</p>}
                <button type="button" className="round-call start" onClick={start} aria-label="Call again">
                  <Phone size={30} aria-hidden="true" />
                </button>
                <p className="round-label">Call again</p>
              </>
            )}
          </section>

          <aside className={`side-panel side-captions ${captions ? '' : 'is-hidden'}`} aria-label="Live captions">
            <p className="eyebrow">Live captions <span>Last 8 lines</span></p>
            {transcriptList}
          </aside>
        </div>
      </main>
    </SessionProvider>
  );
}
