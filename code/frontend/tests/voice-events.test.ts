import { describe, expect, it } from 'vitest';
import { parseVoiceEvent } from '../lib/voice-events';

const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value));

describe('worker browser events', () => {
  it('accepts readiness and safe provider-error feedback', () => {
    expect(parseVoiceEvent(bytes({ type: 'ready', state: 'listening' }))?.type).toBe('ready');
    expect(parseVoiceEvent(bytes({ type: 'error', message: 'Please retry.' }))?.message).toBe('Please retry.');
  });
  it('rejects malformed, unrelated, and oversized packets', () => {
    for (const value of [null, [], { type: 'debug' }, { type: 'error', message: {} },
      { type: 'status', state: 'invalid' }]) expect(parseVoiceEvent(bytes(value))).toBeNull();
    expect(parseVoiceEvent(new TextEncoder().encode('invalid'))).toBeNull();
    expect(parseVoiceEvent(new Uint8Array(3000))).toBeNull();
  });
});
