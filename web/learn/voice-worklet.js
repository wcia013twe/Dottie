// PCM capture stays off the UI thread; the output is silent.
class VoiceCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buffer = new Float32Array(2048); this.offset = 0; }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (input) for (const sample of input) {
      this.buffer[this.offset++] = sample;
      if (this.offset === this.buffer.length) {
        this.port.postMessage(this.buffer);
        this.buffer = new Float32Array(2048); this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor('magneto-voice-capture', VoiceCapture);
