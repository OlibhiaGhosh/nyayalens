import { useCallback, useEffect, useRef, useState } from "react";

const RATE = 16000; // what Gemma's audio encoder expects
export const MAX_SECONDS = 30;

/**
 * Microphone recorder producing a 16 kHz mono 16-bit WAV, entirely in the browser.
 * (MediaRecorder gives webm/opus, which Ollama does not accept, and the browser's
 * SpeechRecognition sends audio to a cloud service, so neither is used.)
 */
export function useRecorder(onDone: (wav: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<"denied" | "unsupported" | null>(null);
  const ctx = useRef<{ stop: () => void } | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  const stop = useCallback(() => ctx.current?.stop(), []);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) return setError("unsupported");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      return setError("denied");
    }
    const ac = new AudioContext();
    const src = ac.createMediaStreamSource(stream);
    const proc = ac.createScriptProcessor(4096, 1, 1);
    const chunks: Float32Array[] = [];
    let n = 0;
    let stopped = false;
    const finish = () => {
      if (stopped) return;
      stopped = true;
      ctx.current = null;
      proc.disconnect();
      src.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      ac.close();
      clearInterval(timer);
      setRecording(false);
      doneRef.current(toWav(chunks, ac.sampleRate));
    };
    proc.onaudioprocess = (e) => {
      chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      n += e.inputBuffer.length;
      if (n >= ac.sampleRate * MAX_SECONDS) finish();
    };
    src.connect(proc);
    proc.connect(ac.destination); // needed for onaudioprocess to fire; the output stays silent
    const t0 = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - t0) / 1000)), 250);
    ctx.current = { stop: finish };
    setSeconds(0);
    setRecording(true);
  }, []);

  useEffect(() => () => ctx.current?.stop(), []);

  return { start, stop, recording, seconds, error };
}

function toWav(chunks: Float32Array[], inRate: number): Blob {
  const total = chunks.reduce((a, c) => a + c.length, 0);
  const input = new Float32Array(total);
  let off = 0;
  for (const c of chunks) {
    input.set(c, off);
    off += c.length;
  }
  // Downsample by averaging each output sample's window (a simple low-pass).
  const ratio = inRate / RATE;
  const len = Math.floor(total / ratio);
  const pcm = new Int16Array(len);
  for (let i = 0; i < len; i++) {
    const a = Math.floor(i * ratio);
    const b = Math.min(total, Math.max(a + 1, Math.floor((i + 1) * ratio)));
    let sum = 0;
    for (let j = a; j < b; j++) sum += input[j];
    const v = Math.max(-1, Math.min(1, sum / (b - a)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.byteLength);
  const dv = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((ch, i) => dv.setUint8(o + i, ch.charCodeAt(0)));
  str(0, "RIFF");
  dv.setUint32(4, 36 + pcm.byteLength, true);
  str(8, "WAVE");
  str(12, "fmt ");
  dv.setUint32(16, 16, true);
  dv.setUint16(20, 1, true); // PCM
  dv.setUint16(22, 1, true); // mono
  dv.setUint32(24, RATE, true);
  dv.setUint32(28, RATE * 2, true);
  dv.setUint16(32, 2, true);
  dv.setUint16(34, 16, true);
  str(36, "data");
  dv.setUint32(40, pcm.byteLength, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}
