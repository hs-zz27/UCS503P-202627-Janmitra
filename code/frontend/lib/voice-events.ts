export type VoiceEvent = {
  type: 'ready' | 'status' | 'error';
  state?: 'listening' | 'thinking' | 'speaking';
  message?: string;
};

export function parseVoiceEvent(payload: Uint8Array): VoiceEvent | null {
  if (payload.byteLength > 2048) return null;
  try {
    const value = JSON.parse(new TextDecoder().decode(payload));
    if (!value || typeof value !== 'object' || Array.isArray(value)
      || !['ready', 'status', 'error'].includes(value.type)
      || (value.state !== undefined && !['listening', 'thinking', 'speaking'].includes(value.state))
      || (value.message !== undefined && typeof value.message !== 'string')) return null;
    return { type: value.type, state: value.state, message: value.message?.slice(0, 300) };
  } catch { return null; }
}
