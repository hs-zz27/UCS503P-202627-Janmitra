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
  Minus,
  Phone,
  Plus,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react';
import { parseVoiceEvent } from '../lib/voice-events';

const AGENT_NAME = process.env.NEXT_PUBLIC_LIVEKIT_AGENT_NAME || 'janmitra-agent';
const MAX_VOLUME = 10;

type Screen = 'idle' | 'connecting' | 'active' | 'ended';

function formatTime(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

// Status-bar clock, read from the device clock after hydration.
function subscribeClock(onChange: () => void) {
  const timer = window.setInterval(onChange, 15000);
  return () => window.clearInterval(timer);
}
function readClock() {
  return new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).replace(/\s?[AP]M$/, '');
}
function serverClock() {
  return '9:41';
}

function StatusBar() {
  const clock = useSyncExternalStore(subscribeClock, readClock, serverClock);
  return (
    <div className="status-bar" aria-hidden="true">
      <span className="status-time">{clock}</span>
      <span className="status-icons">
        <svg className="icon-signal" viewBox="0 0 17 11"><rect x="0" y="7" width="3" height="4" rx="0.7" /><rect x="4.67" y="5" width="3" height="6" rx="0.7" /><rect x="9.33" y="2.5" width="3" height="8.5" rx="0.7" /><rect x="14" y="0" width="3" height="11" rx="0.7" /></svg>
        <svg className="icon-wifi" viewBox="0 0 16 11"><path d="M8 2.3c2.2 0 4.2.8 5.7 2.2l1.1-1.1A9.6 9.6 0 0 0 8 .7 9.6 9.6 0 0 0 1.2 3.4l1.1 1.1A8 8 0 0 1 8 2.3Z" /><path d="M8 5.6c1.3 0 2.5.5 3.4 1.3l1.1-1.1A6.4 6.4 0 0 0 8 4a6.4 6.4 0 0 0-4.5 1.8l1.1 1.1c.9-.8 2.1-1.3 3.4-1.3Z" /><path d="M8 8.4c.5 0 1 .2 1.3.5L8 10.3 6.7 8.9c.3-.3.8-.5 1.3-.5Z" /></svg>
        <svg className="icon-battery" viewBox="0 0 25 12"><rect className="battery-shell" x="0.5" y="0.5" width="21" height="11" rx="3" /><rect x="2" y="2" width="18" height="8" rx="1.8" /><path d="M23 4v4c.8-.3 1.3-1.1 1.3-2S23.8 4.3 23 4Z" fillOpacity="0.4" /></svg>
      </span>
    </div>
  );
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
  const captionsRef = useRef<HTMLDivElement>(null);
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
  const lastLine = transcript.at(-1);
  const captionsKey = lastLine ? `${lastLine.id}:${lastLine.message.length}` : '';

  // Keep the newest caption line in view, as iOS Live Captions does.
  useEffect(() => {
    const panel = captionsRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [captionsKey, captions, screen]);

  const errorLine = displayError
    && <p className="call-error" role="alert"><CircleAlert size={16} aria-hidden="true" />{displayError}</p>;
  const controlsDisabled = screen !== 'active';

  const controls = (
    <div className="control-grid">
      <div className="control">
        <button type="button" className={`round ${muted ? 'is-on' : ''}`} onClick={toggleMute}
          disabled={controlsDisabled} aria-pressed={muted} aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}>
          {muted ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
        </button>
        <span>{muted ? 'unmute' : 'mute'}</span>
      </div>
      <div className="control">
        <button type="button" className={`round ${speaker ? 'is-on' : ''}`} onClick={() => setSpeaker(!speaker)}
          disabled={controlsDisabled} aria-pressed={speaker} aria-label="Speaker">
          {speaker ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
        </button>
        <span>speaker</span>
      </div>
      <div className="control">
        <button type="button" className={`round ${captions ? 'is-on' : ''}`} onClick={() => setCaptions(!captions)}
          disabled={controlsDisabled} aria-pressed={captions} aria-label="Captions">
          <Captions aria-hidden="true" />
        </button>
        <span>captions</span>
      </div>
      <div className="control">
        <button type="button" className="round" onClick={() => setVolume(Math.max(0, volume - 1))}
          disabled={controlsDisabled || volume === 0} aria-label="Volume down">
          <Minus aria-hidden="true" />
        </button>
        <span>vol −</span>
      </div>
      <div className="control">
        <div className={`round meter ${controlsDisabled ? 'is-disabled' : ''}`} role="meter" aria-label="Volume"
          aria-valuemin={0} aria-valuemax={MAX_VOLUME} aria-valuenow={volume}>
          <span className="meter-ring" aria-hidden="true"
            style={{ '--level': `${(volume / MAX_VOLUME) * 100}%` } as CSSProperties} />
          <span className="meter-value" aria-hidden="true">{volume}</span>
        </div>
        <span>volume</span>
      </div>
      <div className="control">
        <button type="button" className="round" onClick={() => setVolume(Math.min(MAX_VOLUME, volume + 1))}
          disabled={controlsDisabled || volume === MAX_VOLUME} aria-label="Volume up">
          <Plus aria-hidden="true" />
        </button>
        <span>vol +</span>
      </div>
    </div>
  );

  return (
    <SessionProvider session={session}>
      <RoomAudioRenderer volume={speaker ? volume / MAX_VOLUME : 0} />
      <div className="stage">
        <div className="device">
          <span className="device-buttons" aria-hidden="true" />
          <section className={`screen is-${screen}`} aria-live="polite" aria-label="Janmitra call">
            <div className="notch" aria-hidden="true"><span className="notch-speaker" /><span className="notch-camera" /></div>
            <StatusBar />

            <header className="caller">
              <h3 className="caller-name">Janmitra AI</h3>
              {screen === 'idle' && <p className="caller-status">Public information helpline</p>}
              {screen === 'connecting' && <p className="caller-status">calling…</p>}
              {screen === 'active' && (
                <p className="caller-status">
                  <span className="caller-timer">{formatTime(seconds)}</span>
                  <span className={`caller-state ${muted ? 'is-muted' : ''}`}>{status}</span>
                </p>
              )}
              {screen === 'ended' && <p className="caller-status">Call ended · {formatTime(seconds)}</p>}
            </header>

            <div className="call-middle">
              {screen === 'idle' && (
                <div className="idle-panel">
                  <p className="call-hint">
                    Ask about crop insurance, pensions, housing, or support for a small business.
                  </p>
                  <label className="access-code">
                    Access code (if required)
                    <input type="password" value={accessCode} autoComplete="off"
                      onChange={(event) => setAccessCode(event.target.value)} />
                  </label>
                  {errorLine}
                </div>
              )}

              {screen === 'connecting' && <p className="call-hint">Allow microphone access when asked.</p>}

              {screen === 'active' && (
                <>
                  {errorLine}
                  {captions && (
                    <div className="live-captions">
                      <p className="live-captions-title"><Captions size={13} aria-hidden="true" />Live Captions</p>
                      <div className="live-captions-scroll" ref={captionsRef}>
                      {transcript.length === 0
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
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}

              {screen === 'ended' && (
                <div className="idle-panel">
                  <p className="call-hint">Official decisions remain with the responsible department.</p>
                  {errorLine}
                </div>
              )}
            </div>

            {(screen === 'connecting' || screen === 'active') && controls}

            <div className="call-action">
              {screen === 'idle' && (
                <button type="button" className="call-button start" onClick={start} aria-label="Call Janmitra">
                  <Phone aria-hidden="true" />
                </button>
              )}
              {screen === 'connecting' && (
                <button type="button" className="call-button end" disabled aria-label="Connecting">
                  <Phone aria-hidden="true" />
                </button>
              )}
              {screen === 'active' && (
                <button type="button" className="call-button end" onClick={stop} aria-label="End call">
                  <Phone aria-hidden="true" />
                </button>
              )}
              {screen === 'ended' && (
                <button type="button" className="call-button start" onClick={start} aria-label="Call again">
                  <Phone aria-hidden="true" />
                </button>
              )}
              {(screen === 'idle' || screen === 'ended') && (
                <span className="call-label">{screen === 'idle' ? 'Call' : 'Call again'}</span>
              )}
            </div>

            <span className="home-indicator" aria-hidden="true" />
          </section>
        </div>
      </div>
    </SessionProvider>
  );
}
