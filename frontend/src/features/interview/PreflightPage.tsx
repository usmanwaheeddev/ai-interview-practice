import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest, ApiError, API_URL } from "../../lib/api";
import type { MockInterview } from "../../lib/types";
import { startMicCapture, type MicCapture } from "./audio";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";

export function PreflightPage() {
  const { interviewId } = useParams();
  const navigate = useNavigate();
  const [interview, setInterview] = useState<MockInterview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const stream = useRef<MediaStream | null>(null);
  const capture = useRef<MicCapture | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    // Self-hosted STT/TTS load their models lazily on first use (see
    // app/main.py's /ready docstring and providers/stt/faster_whisper.py) —
    // several seconds on CPU. Nothing else ever called /ready, so that cold
    // load used to happen during the candidate's actual first turn instead
    // of here, while they're still reading instructions and granting mic
    // access. Fire-and-forget: this is a warmup, not a precondition for
    // continuing, so a failure here shouldn't block the flow.
    void fetch(new URL("/ready", API_URL).toString()).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const poll = async () => {
      try {
        const data = await apiRequest<MockInterview>(`/mock-interviews/${interviewId}`);
        if (cancelled) return;
        setInterview(data);
        if (["completed", "scoring", "scored"].includes(data.state)) {
          navigate(`/mock-interviews/${interviewId}/report`, {replace: true});
        } else if (data.state === "preparing") {
          if (++attempts < 90) timer = setTimeout(() => void poll(), 2000);
          else setError("Preparation is taking longer than expected. Retry preparation below.");
        } else if (data.state === "failed") {
          setError(data.failure_reason ?? "Could not prepare interview.");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load interview.");
      }
    };
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [interviewId, navigate, retry]);

  useEffect(() => () => {
    capture.current?.stop();
    stream.current?.getTracks().forEach(t => t.stop());
  }, []);

  const allow = async () => {
    setBusy(true); setError(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({audio: true, video: interview?.video_enabled ?? false});
      stream.current = media;
      capture.current = startMicCapture(media, () => {}, setLevel);
      setAllowed(true);
    } catch { setError("Allow microphone access in browser settings to continue."); }
    finally { setBusy(false); }
  };

  const begin = async () => {
    setBusy(true);
    try {
      await apiRequest(`/mock-interviews/${interviewId}/consent`, {method:"POST"});
      capture.current?.stop();
      stream.current?.getTracks().forEach(t => t.stop());
      navigate(`/mock-interviews/${interviewId}/room`);
    } catch(err) { setError(err instanceof ApiError ? err.message : "Could not start interview."); setBusy(false); }
  };

  const retryPlan = async () => {
    setError(null); setBusy(true);
    try {
      await apiRequest(`/mock-interviews/${interviewId}/retry`, {method:"POST"});
      setRetry(n => n + 1);
    } catch(err) { setError(err instanceof ApiError ? err.message : "Could not retry."); }
    finally { setBusy(false); }
  };

  return <div className="mx-auto flex max-w-xl flex-col gap-5 px-6 py-10">
    <h1 className="text-2xl font-semibold">{interview?.state === "preparing" ? "Preparing your interview" : "Before you begin"}</h1>
    {error && <Alert>{error}</Alert>}
    {interview?.state === "preparing" && <p>Building your interview questions…</p>}
    {interview && ["ready","disconnected","in_progress"].includes(interview.state) && <>
      <p>{interview.duration_minutes}-minute practice interview. {interview.video_enabled ? "Camera and microphone" : "Microphone only"}. You may end early and practise again in a new interview.</p>
      <Button disabled={busy || allowed} onClick={() => void allow()}>{allowed ? "Microphone ready" : interview.video_enabled ? "Allow camera and microphone" : "Allow microphone"}</Button>
      {allowed && <div className="level-meter" aria-label="Microphone level"><div className="level-meter-fill" style={{width: `${Math.min(100, level * 400)}%`}} /></div>}
      {allowed && interview.video_enabled && <video autoPlay muted playsInline ref={element => { video.current = element; if (element) element.srcObject = stream.current; }} />}
      <label className="flex gap-2"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />I consent to recording and AI feedback for my private practice report.</label>
      <Button disabled={busy || !allowed || !consent} onClick={() => void begin()}>Begin interview</Button>
    </>}
    {error && interview && ["preparing","failed"].includes(interview.state) && <Button disabled={busy} onClick={() => void retryPlan()}>Retry preparation</Button>}
    <Link to="/mock-interviews">My interviews</Link>
    <Link to="/privacy-notice">Privacy notice</Link>
  </div>;
}
