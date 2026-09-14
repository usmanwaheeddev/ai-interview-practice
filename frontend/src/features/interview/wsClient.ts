export interface SessionStateMsg {
  state: string;
  elapsed_s: number;
  remaining_s: number;
  turn_index: number;
}
export interface TranscriptMsg {
  turn_id: number | string;
  text: string;
  /** The spoken language auto-detected from this candidate utterance
   * (en/hi/ur) — the conversation follows whatever the candidate speaks. */
  language?: string;
}
export interface CandidateProcessingMsg {
  type: "candidate.processing";
}
export interface AgentSpeakingMsg {
  turn_id: number | string;
  text?: string;
  question_source?: string | null;
  /** The spoken language this utterance is voiced in. */
  language?: string;
}
export interface TimerTickMsg {
  elapsed_s: number;
  remaining_s: number;
}
export interface ErrorMsg {
  code: string;
  message?: string;
  recoverable: boolean;
}

export interface InterviewWSHandlers {
  onSessionState?: (msg: SessionStateMsg) => void;
  onTranscriptFinal?: (msg: TranscriptMsg) => void;
  onTranscriptPartial?: (msg: TranscriptMsg) => void;
  onCandidateProcessing?: (msg: CandidateProcessingMsg) => void;
  onAgentSpeakingStart?: (msg: AgentSpeakingMsg) => void;
  onAudioChunk?: (bytes: ArrayBuffer) => void;
  onAgentSpeakingEnd?: (msg: AgentSpeakingMsg) => void;
  onTimerTick?: (msg: TimerTickMsg) => void;
  onSessionComplete?: (reason: string) => void;
  onError?: (msg: ErrorMsg) => void;
  onOpen?: () => void;
  /** code 4001 = consent not recorded yet (app-defined, see app/ws/interview.py);
   * 1008 = auth/policy rejection. Neither should trigger a reconnect loop. */
  onClose?: (code: number) => void;
}

const MAX_RECONNECT_DELAY_MS = 30_000;
const NO_RECONNECT_CODES = new Set([1000, 1008, 4001, 4009]);

export class InterviewSocket {
  private ws: WebSocket | null = null;
  private manualClose = false;
  private reconnectAttempt = 0;
  private reconnectTimer: number | null = null;
  private sampleRate = 16000;

  constructor(
    private sessionId: string,
    private handlers: InterviewWSHandlers,
  ) {}

  connect(sampleRate: number): void {
    this.sampleRate = sampleRate;
    this.manualClose = false;
    this._connect();
  }

  private _connect(): void {
    const wsBase =
      import.meta.env.VITE_WS_URL ??
      `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8005`;
    const ws = new WebSocket(`${wsBase}/ws/mock-interviews/${this.sessionId}`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectAttempt = 0;
      ws.send(JSON.stringify({ type: "session.start", sample_rate: this.sampleRate }));
      this.handlers.onOpen?.();
    };

    ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      if (typeof event.data === "string") {
        this.dispatch(JSON.parse(event.data));
      } else {
        this.handlers.onAudioChunk?.(event.data);
      }
    };

    ws.onclose = (event: CloseEvent) => {
      this.handlers.onClose?.(event.code);
      if (!this.manualClose && !NO_RECONNECT_CODES.has(event.code)) {
        this.scheduleReconnect();
      }
    };
  }

  private dispatch(msg: Record<string, unknown>): void {
    switch (msg.type) {
      case "session.state":
        this.handlers.onSessionState?.(msg as unknown as SessionStateMsg);
        break;
      case "transcript.final":
        this.handlers.onTranscriptFinal?.(msg as unknown as TranscriptMsg);
        break;
      case "transcript.partial":
        this.handlers.onTranscriptPartial?.(msg as unknown as TranscriptMsg);
        break;
      case "candidate.processing":
        this.handlers.onCandidateProcessing?.(msg as unknown as CandidateProcessingMsg);
        break;
      case "agent.speaking_start":
        this.handlers.onAgentSpeakingStart?.(msg as unknown as AgentSpeakingMsg);
        break;
      case "agent.speaking_end":
        this.handlers.onAgentSpeakingEnd?.(msg as unknown as AgentSpeakingMsg);
        break;
      case "timer.tick":
        this.handlers.onTimerTick?.(msg as unknown as TimerTickMsg);
        break;
      case "session.complete":
        this.handlers.onSessionComplete?.(String(msg.reason));
        break;
      case "error":
        this.handlers.onError?.(msg as unknown as ErrorMsg);
        break;
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempt += 1;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempt, MAX_RECONNECT_DELAY_MS);
    this.reconnectTimer = window.setTimeout(() => this._connect(), delay);
  }

  sendAudioChunk(pcm: ArrayBuffer): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(pcm);
  }

  endInterview(): void { this.sendJson({type: "session.end"}); }

  private sendJson(obj: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
  }

  close(): void {
    this.manualClose = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.ws?.close(1000);
  }
}
