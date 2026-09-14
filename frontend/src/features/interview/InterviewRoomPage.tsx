import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest, ApiError } from "../../lib/api";
import type { MockInterview } from "../../lib/types";
import { AudioPlaybackQueue, startMicCapture, type MicCapture } from "./audio";
import { ChunkedMediaUploader } from "./mediaUpload";
import { InterviewSocket } from "./wsClient";
import { StatusPill } from "../../components/ui/StatusPill";
import { Button } from "../../components/ui/Button";
import { Alert } from "../../components/ui/Alert";
import { Spinner } from "../../components/ui/Spinner";

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

const statusTone = {
  connected: "success",
  connecting: "neutral",
  reconnecting: "warning",
  disconnected: "danger",
} as const;

interface TranscriptEntry {
  speaker: "agent" | "candidate";
  text: string;
  questionSource?: string | null;
}

// Mic level (0-1ish RMS) above which the candidate waveform animates as
// "speaking" — well below the old barge-in threshold since this is now
// purely a visual "are you being heard" indicator, not an interrupt trigger.
const CANDIDATE_SPEAKING_LEVEL = 0.02;

export function InterviewRoomPage() {
  const { interviewId } = useParams<{ interviewId: string }>();
  const navigate = useNavigate();

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [remainingS, setRemainingS] = useState<number | null>(null);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [candidateSpeaking, setCandidateSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  // True in the gap between the candidate's answer being transcribed and the
  // interviewer's next turn arriving — that gap runs real STT/LLM/TTS calls
  // that can take a few seconds, so it gets its own visible loading state
  // rather than leaving the candidate looking at a static screen.
  const [processing, setProcessing] = useState(false);
  const [endingInterview, setEndingInterview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeLlm, setActiveLlm] = useState<"groq" | "ollama" | null>(null);

  const socketRef = useRef<InterviewSocket | null>(null);
  const playbackRef = useRef<AudioPlaybackQueue | null>(null);
  const micCaptureRef = useRef<MicCapture | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const uploaderRef = useRef<ChunkedMediaUploader | null>(null);
  const transcriptScrollRef = useRef<HTMLElement | null>(null);
  // Server-authoritative "is it currently the interviewer's turn" — set
  // directly from agent.speaking_start/end (not React state, so the mic
  // capture closure below always sees the latest value with no render lag).
  const interviewerTurnRef = useRef(false);
  // Client-side "is the interviewer's audio still actually playing" — the
  // server's agent.speaking_end fires the instant it finishes *transmitting*
  // TTS bytes, well before playback finishes on this end (playback can run
  // many seconds behind for a long utterance, worst on the first turn's
  // greeting). Gating the mic on interviewerTurnRef alone let the candidate's
  // mic go live while the interviewer's own voice was still audible, so it
  // got picked up as if it were the answer. Mirrors AudioPlaybackQueue's
  // onSpeakingChange, which has its own 60s stuck-fallback (see audio.ts), so
  // this can't wedge the mic permanently the way keying off it used to worry.
  const agentPlaybackRef = useRef(false);
  // Pause outgoing microphone frames as soon as the server detects the end
  // of an answer. Otherwise audio recorded during STT/LLM processing queues
  // in the WebSocket and is consumed as the next answer after the agent turn.
  const processingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    playbackRef.current = new AudioPlaybackQueue((speaking) => {
      agentPlaybackRef.current = speaking;
      setAgentSpeaking(speaking);
    });

    const setup = async () => {
      const session = await apiRequest<MockInterview>(
        `/mock-interviews/${interviewId}`,
      );
      if (cancelled) return;
      setRemainingS(session.remaining_s);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
        video: session.video_enabled,
      });
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;

      // Store a private recording for the candidate's own report. Audio-only
      // practice never asks for or records a camera stream.
      uploaderRef.current = new ChunkedMediaUploader(session.id, session.video_enabled ? "video" : "audio");
      const recorder = new MediaRecorder(stream, {
        mimeType: session.video_enabled ? "video/webm" : "audio/webm",
      });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) uploaderRef.current?.uploadChunk(event.data);
      };
      recorder.start(10_000); // 10s timeslices — chunked, not one giant blob
      recorderRef.current = recorder;


      const socket = new InterviewSocket(session.id, {
        onOpen: () => setStatus("connected"),
        onClose: (code) => {
          processingRef.current = false;
          setProcessing(false);
          if (code !== 1000) setEndingInterview(false);
          if ([1000, 1008, 4001, 4009].includes(code)) {
            setStatus("disconnected");
            if (code !== 1000) setError("Connection rejected. Return to your interviews and check consent or sign in again.");
          } else setStatus("reconnecting");
        },
        onSessionState: (msg) => setRemainingS(msg.remaining_s),
        onTimerTick: (msg) => setRemainingS(msg.remaining_s),
        onCandidateProcessing: () => {
          processingRef.current = true;
          setCandidateSpeaking(false);
          setProcessing(true);
        },
        onTranscriptPartial: (msg) => {
          setError(null);
          setPartialTranscript(msg.text);
        },
        onTranscriptFinal: (msg) => {
          setError(null);
          setPartialTranscript("");
          setTranscript((prev) => [...prev, { speaker: "candidate", text: msg.text }]);
          setProcessing(true); // waiting on the interviewer's next turn now
        },
        onAgentSpeakingStart: (msg) => {
          setError(null);
          processingRef.current = false;
          interviewerTurnRef.current = true;
          setProcessing(false);
          if (msg.question_source === "groq" || msg.question_source === "ollama") {
            setActiveLlm(msg.question_source);
          }
          setTranscript((prev) => [
            ...prev,
            {
              speaker: "agent",
              text: msg.text ?? "",
              questionSource: msg.question_source,
            },
          ]);
        },
        // The server-authoritative bracket around the agent's turn — sent
        // whether or not TTS actually produced audio (see app/ws/interview.py
        // speak()). The mic gate below keys off this, not off whether the
        // browser's <audio> element has finished playing: that's a
        // best-effort UI signal (see AudioPlaybackQueue) that can occasionally
        // never fire its "ended" event, and gating the mic on it would then
        // silence the candidate for the rest of the session with no recovery.
        onAgentSpeakingEnd: () => {
          interviewerTurnRef.current = false;
        },
        onAudioChunk: (bytes) => playbackRef.current?.enqueue(bytes),
        onSessionComplete: async () => {
          processingRef.current = false;
          setStatus("disconnected");
          setProcessing(false);
          micCaptureRef.current?.stop();
          socketRef.current?.close();
          const recording = recorderRef.current;
          if (recording && recording.state !== "inactive") {
            await new Promise<void>(resolve => { recording.addEventListener("stop", () => resolve(), {once:true}); recording.stop(); });
          }
          streamRef.current?.getTracks().forEach(t => t.stop());
          try { await uploaderRef.current?.complete(); } catch { /* Report remains available if recording upload fails. */ }
          navigate(`/mock-interviews/${interviewId}/report`);
        },
        onError: (msg) => {
          setPartialTranscript("");
          processingRef.current = false;
          setProcessing(false);
          setError(msg.message ?? msg.code);
        },
      });
      socketRef.current = socket;

      // Don't capture or send the candidate's mic while the interviewer is
      // speaking (server-authoritative turn state, or the interviewer's TTS
      // audio still actually playing back here — whichever ends later), or
      // while the candidate has muted themselves — a real interviewer isn't
      // listening for an answer while still asking the question, and neither
      // should this.
      const micCapture = startMicCapture(
        stream,
        (pcm) => {
          if (
            !interviewerTurnRef.current &&
            !agentPlaybackRef.current &&
            !processingRef.current &&
            !mutedRef.current
          ) {
            socketRef.current?.sendAudioChunk(pcm);
          }
        },
        (level) => {
          setCandidateSpeaking(
            !interviewerTurnRef.current &&
              !agentPlaybackRef.current &&
              !processingRef.current &&
              !mutedRef.current &&
              level > CANDIDATE_SPEAKING_LEVEL,
          );
        },
      );
      micCaptureRef.current = micCapture;
      // Browsers may reject the requested 16 kHz AudioContext and fall back
      // to the device rate (commonly 48 kHz). Tell the server the rate that
      // is actually being sent so VAD timing and Whisper input stay correct.
      socket.connect(micCapture.sampleRate);

    };

    setup()
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not start the interview room");
        }
      });

    return () => {
      cancelled = true;
      socketRef.current?.close();
      micCaptureRef.current?.stop();
      if (recorderRef.current?.state !== "inactive") recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one-time setup by design
  }, [interviewId]);

  // Kept in a ref (not state) so the mic-capture closure above always reads
  // the latest value without needing to be torn down and rebuilt every time
  // muted changes.
  const mutedRef = useRef(muted);
  useEffect(() => {
    mutedRef.current = muted;
    if (muted) setCandidateSpeaking(false);
  }, [muted]);

  // Keep both finalized turns and the changing partial STT line visible.
  // Assigning the container's own scrollTop avoids moving the whole page,
  // which scrollIntoView can do when the interview room is taller than the
  // viewport.
  useEffect(() => {
    const container = transcriptScrollRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [transcript, partialTranscript]);

  const endInterview = () => {
    setEndingInterview(true);
    setProcessing(false);
    setAgentSpeaking(false);
    setCandidateSpeaking(false);
    processingRef.current = true;
    interviewerTurnRef.current = false;
    agentPlaybackRef.current = false;
    playbackRef.current?.stop();
    micCaptureRef.current?.stop();
    micCaptureRef.current = null;
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    socketRef.current?.endInterview();
  };

  // The server only pushes an authoritative remaining_s every few seconds
  // (or longer, if it's mid-STT/LLM/TTS on the current turn) — displaying
  // that alone made the clock visibly jump instead of counting down. This
  // ticks it down locally every second between server updates for a smooth
  // display; each server message still snaps `remainingS` to the true value
  // (see onSessionState/onTimerTick above), so this can't drift for long.
  // Tied to `status` so it stops decrementing the moment the connection is
  // lost and only resumes once reconnected and re-synced.
  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => {
      setRemainingS((current) => (current !== null ? Math.max(0, current - 1) : current));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status]);

  const minutes = remainingS !== null ? Math.floor(remainingS / 60) : null;
  const seconds = remainingS !== null ? remainingS % 60 : null;

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-8">
      <header className="flex items-center justify-between">
        <StatusPill tone={statusTone[status]} className="items-center gap-1.5">
          {(status === "connecting" || status === "reconnecting") && <Spinner className="h-3 w-3" />}
          {status === "connected" && "Connected"}
          {status === "connecting" && "Connecting…"}
          {status === "reconnecting" && "Reconnecting…"}
          {status === "disconnected" && "Disconnected"}
        </StatusPill>
        {minutes !== null && seconds !== null && (
          <span className="font-mono text-lg font-semibold tabular-nums text-ink-900">
            {minutes}:{seconds.toString().padStart(2, "0")} remaining
          </span>
        )}
      </header>

      <div className="flex flex-wrap gap-3">
        <Button
          variant="secondary"
          onClick={() => setMuted((current) => !current)}
          disabled={status === "disconnected"}
          aria-pressed={muted}
        >
          {muted ? "Unmute microphone" : "Mute microphone"}
        </Button>
        <Button variant="secondary" onClick={endInterview} disabled={status !== "connected" || endingInterview}>
          {endingInterview ? <><Spinner className="h-4 w-4" /> Ending interview…</> : "End interview and get feedback"}
        </Button>
        {muted && <StatusPill tone="warning">Microphone muted</StatusPill>}
        {activeLlm && <StatusPill tone="info">LLM: {activeLlm === "groq" ? "Groq" : "Ollama"}</StatusPill>}
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col items-center gap-2">
          <span className="text-xs font-medium text-ink-500">Interviewer</span>
          <div
            className={`waveform flex h-16 items-center justify-center gap-1 ${agentSpeaking ? "speaking" : ""}`}
            aria-hidden="true"
          >
            <div className="waveform-bar" />
            <div className="waveform-bar" />
            <div className="waveform-bar" />
          </div>
        </div>
        <div className="flex flex-col items-center gap-2">
          <span className="text-xs font-medium text-ink-500">You{muted ? " (muted)" : ""}</span>
          <div
            className={`waveform flex h-16 items-center justify-center gap-1 ${candidateSpeaking ? "speaking" : ""}`}
            aria-hidden="true"
          >
            <div className="waveform-bar" />
            <div className="waveform-bar" />
            <div className="waveform-bar" />
          </div>
        </div>
      </div>

      {processing && !agentSpeaking && (
        <div className="flex items-center gap-2 text-sm text-ink-500">
          <Spinner className="h-4 w-4" />
          {transcript.at(-1)?.speaker === "candidate"
            ? "Your answer was transcribed. Interviewer is thinking…"
            : "Transcribing your answer…"}
        </div>
      )}

      <section
        ref={transcriptScrollRef}
        className="flex max-h-[28rem] flex-col gap-3 overflow-y-auto rounded-lg border border-ink-300/70 bg-white p-4 shadow-card"
        aria-label="Live speech-to-text transcript"
      >
        <h2 className="text-sm font-semibold text-ink-900">Live transcript (speech-to-text)</h2>
        {!transcript.length && (
          <p className="m-0 text-sm text-ink-500">
            Your recognized answers will appear here after you finish speaking.
          </p>
        )}
        {transcript.map((entry, i) => (
          <p
            key={i}
            dir="ltr"
            className={`m-0 text-sm leading-relaxed ${
              entry.speaker === "candidate" ? "text-ink-500" : "text-ink-900"
            }`}
          >
            <strong className="font-semibold text-ink-900">
              {entry.speaker === "agent" ? "Interviewer" : "You"}:
            </strong>{" "}
            {entry.speaker === "agent" &&
              (entry.questionSource === "groq" || entry.questionSource === "ollama") && (
              <StatusPill
                tone="info"
                className="mr-2 align-middle"
              >
                {entry.questionSource === "groq"
                  ? "Groq"
                  : "Ollama"}
              </StatusPill>
            )}
            {entry.text}
          </p>
        ))}
        {partialTranscript && (
          <p dir="ltr" className="m-0 text-sm italic leading-relaxed text-ink-500">
            <strong className="font-semibold text-ink-900">You (transcribing):</strong>{" "}
            {partialTranscript}
          </p>
        )}
      </section>
    </div>
  );
}
