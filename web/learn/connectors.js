/** Camera frames use the local recognizer; voice uses a separate ElevenLabs streaming adapter; physical Braille remains unintegrated. */
export const connectors = Object.freeze({
  camera: { status: 'available', async observe(jpeg, signal) { const response = await fetch('/api/explore-observe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jpeg }), signal }); let result; try { result = await response.json(); } catch { throw new Error('Recognition needs the local Magneto server.'); } if (!response.ok) throw new Error(result.error || 'Object recognition is unavailable.'); if (!Array.isArray(result.detections) || !Number.isFinite(result.width) || !Number.isFinite(result.height)) throw new Error('Invalid recognition response.'); return result; }, async connect() { if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported'); const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false }); return { connected: true, stream }; } },
  braille: { status: 'not-integrated', async write(word) { return { ready: false, word, reason: 'Braille hardware is not connected.' }; } },
  voiceInput: { status: 'configuration-dependent', provider: 'elevenlabs-scribe-v2-realtime', tokenEndpoint: '/api/voice-token' }
});
// Future adapters: objectSelected({ label, confidence }), write(word), ready({ word }).
// Only an actual hardware acknowledgement may announce physical Braille as ready.
