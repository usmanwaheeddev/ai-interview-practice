/**
 * Mic capture -> 16-bit PCM chunks ("binary frame,
 * 16 kHz mono PCM, ~250 ms") and sequential playback of agent audio.
 *
 * Uses ScriptProcessorNode rather than AudioWorklet — it's deprecated but
 * universally supported and needs no separate worklet module file served
 * and loaded via URL. Documented tech debt, not an oversight: revisit if
 * ScriptProcessorNode is ever actually removed from browsers, which hasn't
 * happened despite years of deprecation warnings.
 */

const TARGET_SAMPLE_RATE = 16000;
const BUFFER_SIZE = 4096; // ~256ms at 16kHz

export function float32ToPCM16(input: Float32Array): ArrayBuffer {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output.buffer;
}

export function rms(input: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
  return Math.sqrt(sum / input.length);
}

export interface MicCapture {
  sampleRate: number;
  stop: () => void;
}

/**
 * `onChunk` fires ~every BUFFER_SIZE samples with raw PCM16 bytes.
 * `onLevel` fires with each chunk's RMS (0-1ish) — for a level meter, should
 * one get built later.
 */
export function startMicCapture(
  stream: MediaStream,
  onChunk: (pcm: ArrayBuffer) => void,
  onLevel?: (level: number) => void,
): MicCapture {
  const AudioContextCtor =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

  let audioContext: AudioContext;
  try {
    audioContext = new AudioContextCtor({ sampleRate: TARGET_SAMPLE_RATE });
  } catch {
    // Some browsers reject an explicit sampleRate on some devices — fall
    // back to native rate; the server resamples anyway (see
    // app/services/audio.py resample_pcm16_mono), it just costs a bit more
    // there than doing it up front here.
    audioContext = new AudioContextCtor();
  }

  const source = audioContext.createMediaStreamSource(stream);
  // createScriptProcessor is deprecated in favour of AudioWorklet — see
  // module docstring for why this project uses it anyway for now.
  const processor = audioContext.createScriptProcessor(BUFFER_SIZE, 1, 1);

  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0);
    onChunk(float32ToPCM16(input));
    onLevel?.(rms(input));
  };

  source.connect(processor);
  // A ScriptProcessorNode only fires onaudioprocess while connected to a
  // destination in most browsers — route through a silent gain node so we
  // don't actually play the candidate's own mic back to them.
  const silentGain = audioContext.createGain();
  silentGain.gain.value = 0;
  processor.connect(silentGain);
  silentGain.connect(audioContext.destination);

  let stopped = false;

  return {
    sampleRate: audioContext.sampleRate,
    stop: () => {
      // End interview, session.complete, and React unmount can all request
      // cleanup. AudioContext.close() throws InvalidStateError when invoked
      // twice, so make the whole capture teardown idempotent.
      if (stopped) return;
      stopped = true;
      processor.disconnect();
      source.disconnect();
      silentGain.disconnect();
      if (audioContext.state !== "closed") void audioContext.close();
    },
  };
}

/** Sequential playback of agent audio chunks (each a complete WAV — see
 * 12's known-limits note: this isn't true streaming
 * playback, since our TTS providers return a complete file, not a stream). */
export class AudioPlaybackQueue {
  private queue: Blob[] = [];
  private playing = false;
  private activeAudio: HTMLAudioElement | null = null;
  private settleCurrent: (() => void) | null = null;
  private generation = 0;

  constructor(private onSpeakingChange?: (speaking: boolean) => void) {}

  enqueue(bytes: ArrayBuffer, mimeType = "audio/wav"): void {
    this.queue.push(new Blob([bytes], { type: mimeType }));
    if (!this.playing) void this.playNext();
  }

  /** Immediately stop current playback and discard every queued utterance. */
  stop(): void {
    this.generation += 1;
    this.queue = [];
    this.activeAudio?.pause();
    this.settleCurrent?.();
    this.activeAudio = null;
    this.settleCurrent = null;
    this.playing = false;
    this.onSpeakingChange?.(false);
  }

  private async playNext(): Promise<void> {
    const generation = this.generation;
    const blob = this.queue.shift();
    if (!blob) {
      this.playing = false;
      this.onSpeakingChange?.(false);
      return;
    }
    this.playing = true;
    this.onSpeakingChange?.(true);

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    this.activeAudio = audio;
    await new Promise<void>((resolve) => {
      // A detached <audio> element occasionally never fires `ended` or
      // `error` in some browsers — without a fallback, that would wedge
      // this queue (and every agent turn enqueued after it) forever, since
      // playNext() only ever gets called again once `playing` goes false.
      const settle = () => {
        window.clearTimeout(timer);
        if (this.settleCurrent === settle) this.settleCurrent = null;
        resolve();
      };
      this.settleCurrent = settle;
      const timer = window.setTimeout(settle, 60_000);
      audio.onended = settle;
      audio.onerror = settle;
      void audio.play().catch(settle);
    });
    if (this.activeAudio === audio) this.activeAudio = null;
    URL.revokeObjectURL(url);
    if (generation !== this.generation) return;
    await this.playNext();
  }
}
