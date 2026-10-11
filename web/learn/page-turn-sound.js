// A brief paper rustle, synthesized locally without external audio assets.
export function createPageTurnSound() {
  let context = null, active = null, disposed = false;
  async function play() {
    if (disposed) return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    try {
      context ||= new AudioContext();
      if (context.state === 'suspended') await context.resume();
      if (disposed || context.state !== 'running') return;
      active?.stop();
      const duration = 0.28;
      const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * duration), context.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
      const source = context.createBufferSource(); source.buffer = buffer;
      const filter = context.createBiquadFilter(); filter.type = 'bandpass'; filter.frequency.value = 1800; filter.Q.value = 0.65;
      const gain = context.createGain(), now = context.currentTime;
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.12, now + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
      source.connect(filter); filter.connect(gain); gain.connect(context.destination);
      active = source;
      source.onended = () => {source.disconnect(); filter.disconnect(); gain.disconnect(); if (active === source) active = null;};
      source.start();
    } catch { /* Reading still works when browser audio is unavailable. */ }
  }
  return {play, dispose() {disposed = true; active?.stop(); active = null; context?.close().catch(() => {});}};
}
