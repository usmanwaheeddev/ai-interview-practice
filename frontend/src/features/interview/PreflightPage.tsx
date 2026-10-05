import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { apiRequest, ApiError, API_URL } from "../../lib/api";
import {
  clearPendingInterview,
  loadPendingInterview,
  loadPendingInterviewId,
  savePendingInterviewId,
} from "../../lib/pendingInterview";
import type { InterviewDraft, MockInterview } from "../../lib/types";
import { areaLabel, INTERVIEW_FIELDS } from "../../lib/interviewFields";
import { startMicCapture, type MicCapture } from "./audio";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageShell } from "../../components/ui/PageShell";
import { Spinner } from "../../components/ui/Spinner";
import { StatusPill } from "../../components/ui/StatusPill";

type SetupIcon = "sparkles" | "clock" | "microphone" | "camera" | "shield" | "check";

function SetupIcon({name, className = "h-5 w-5"}: {name: SetupIcon; className?: string}) {
  const paths: Record<SetupIcon, ReactNode> = {
    sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z"/><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7L19 14ZM5 13l.8 2.2L8 16l-2.2.8L5 19l-.8-2.2L2 16l2.2-.8L5 13Z"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    microphone: <><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></>,
    camera: <><rect x="3" y="6" width="14" height="12" rx="2"/><path d="m17 10 4-2v8l-4-2z"/></>,
    shield: <><path d="M12 3 5 6v5c0 4.5 2.8 8 7 10 4.2-2 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
  };
  return <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

export function PreflightPage() {
  const { interviewId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const navigationState = location.state as {
    activeSection?: "new" | "language";
    draft?: InterviewDraft;
  } | null;
  const [draft] = useState<InterviewDraft | null>(
    () => navigationState?.draft ?? loadPendingInterview(),
  );
  const [interview, setInterview] = useState<MockInterview | null>(null);
  const [createdInterviewId, setCreatedInterviewId] = useState<string | null>(
    () => interviewId ? null : loadPendingInterviewId(),
  );
  const [error, setError] = useState<string | null>(
    !interviewId && !draft ? "Your interview settings are missing. Return and configure the interview again." : null,
  );
  const [allowed, setAllowed] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const stream = useRef<MediaStream | null>(null);
  const capture = useRef<MicCapture | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const mounted = useRef(true);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    // Self-hosted STT/TTS load their models lazily on first use (see
    // app/main.py's /api/ready docstring and providers/stt/faster_whisper.py) —
    // several seconds on CPU. Nothing else ever called /api/ready, so that cold
    // load used to happen during the candidate's actual first turn instead
    // of here, while they're still reading instructions and granting mic
    // access. Fire-and-forget: this is a warmup, not a precondition for
    // continuing, so a failure here shouldn't block the flow.
    void fetch(`${API_URL}/ready`).catch(() => {});
  }, []);

  useEffect(() => {
    if (!interviewId) return;
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

  useEffect(() => {
    // React Strict Mode runs setup -> cleanup -> setup once in development.
    // Restore the flag during setup so the first diagnostic cleanup does not
    // make waitForReady() treat this still-mounted page as closed forever.
    mounted.current = true;
    return () => {
      mounted.current = false;
      capture.current?.stop();
      stream.current?.getTracks().forEach(t => t.stop());
    };
  }, []);

  const allow = async () => {
    setBusy(true); setError(null);
    try {
      const media = await navigator.mediaDevices.getUserMedia({audio: true, video: (interview ?? draft)?.video_enabled ?? false});
      stream.current = media;
      capture.current = startMicCapture(media, () => {}, setLevel);
      setAllowed(true);
    } catch { setError("Allow microphone access in browser settings to continue."); }
    finally { setBusy(false); }
  };

  const waitForReady = async (id: string) => {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      if (!mounted.current) throw new DOMException("Preflight closed", "AbortError");
      const current = await apiRequest<MockInterview>(`/mock-interviews/${id}`);
      if (!mounted.current) throw new DOMException("Preflight closed", "AbortError");
      setInterview(current);
      if (["ready", "disconnected", "in_progress"].includes(current.state)) return current;
      if (current.state === "failed") {
        throw new Error(current.failure_reason ?? "Could not prepare interview.");
      }
      await new Promise(resolve => window.setTimeout(resolve, 2000));
    }
    throw new Error("Preparation is taking longer than expected. Please retry.");
  };

  const begin = async () => {
    setBusy(true);
    setError(null);
    try {
      let id = interviewId ?? createdInterviewId;
      let current = interview;
      if (!id) {
        if (!draft) throw new Error("Interview settings are unavailable.");
        current = await apiRequest<MockInterview>("/mock-interviews", {
          method: "POST",
          body: draft,
        });
        id = current.id;
        setCreatedInterviewId(id);
        savePendingInterviewId(id);
        setInterview(current);
      }
      if (!["ready", "disconnected", "in_progress"].includes(current?.state ?? "")) {
        current = await waitForReady(id);
      }
      await apiRequest(`/mock-interviews/${id}/consent`, {method:"POST"});
      if (!mounted.current) return;
      capture.current?.stop();
      stream.current?.getTracks().forEach(t => t.stop());
      clearPendingInterview();
      navigate(`/mock-interviews/${id}/room`);
    } catch(err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        if (mounted.current) setBusy(false);
        return;
      }
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Could not start interview.");
      setBusy(false);
    }
  };

  const retryPlan = async () => {
    setError(null); setBusy(true);
    try {
      const id = interviewId ?? createdInterviewId;
      if (!id) throw new Error("Interview has not been created yet.");
      const preparing = await apiRequest<MockInterview>(`/mock-interviews/${id}/retry`, {method:"POST"});
      setInterview(preparing);
      if (interviewId) setRetry(n => n + 1);
      else setInterview(await waitForReady(id));
    } catch(err) { setError(err instanceof ApiError || err instanceof Error ? err.message : "Could not retry."); }
    finally { setBusy(false); }
  };

  const configuration = interview ?? draft;
  const isReady = (!interview && Boolean(draft)) || Boolean(interview && ["ready", "disconnected", "in_progress"].includes(interview.state));
  const permissionLabel = configuration?.video_enabled ? "Camera and microphone" : "Microphone";
  const activeSection = interview
    ? interview.language ? "language" as const : "new" as const
    : draft?.language ? "language" as const : navigationState?.activeSection ?? (draft ? "new" : null);
  const focusLabel = configuration?.language
    ? `${configuration.language === "csharp" ? "C#" : configuration.language[0].toUpperCase() + configuration.language.slice(1)} · ${configuration.level ?? "practice"}`
    : configuration?.topics?.map(topic => topic === "all_areas" ? "All areas" : areaLabel(topic)).join(", ") ?? "";
  const fieldLabel = configuration?.field_type
    ? INTERVIEW_FIELDS[configuration.field_type].label
    : null;

  return <PageShell
    title={interview?.state === "preparing" ? "Preparing your interview" : "Interview setup"}
    activeSection={activeSection}
    actions={<Link to="/mock-interviews" className="hidden rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-700 sm:inline-flex">My interviews</Link>}
  >
    <div className="mx-auto max-w-5xl space-y-6">
      {error && <Alert>{error}</Alert>}

      {!interview && !draft && !error && <Card className="flex min-h-64 items-center justify-center gap-3 rounded-2xl border-slate-200 p-10 text-slate-600">
        <Spinner className="h-5 w-5 text-indigo-600" />
        Loading your interview…
      </Card>}

      {interview?.state === "preparing" && <div className="overflow-hidden rounded-2xl border border-indigo-100 bg-white shadow-card">
        <div className="relative overflow-hidden bg-gradient-to-br from-slate-950 via-indigo-950 to-indigo-800 px-7 py-10 text-white sm:px-10 sm:py-12">
          <div className="absolute -right-12 -top-16 h-56 w-56 rounded-full bg-indigo-400/20 blur-3xl" />
          <div className="absolute -bottom-20 left-1/3 h-48 w-48 rounded-full bg-violet-400/20 blur-3xl" />
          <div className="relative max-w-2xl">
            <span className="mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-white/10 text-indigo-200 ring-1 ring-white/15">
              <SetupIcon name="sparkles" className="h-6 w-6" />
            </span>
            <StatusPill className="mb-4 bg-white/10 text-indigo-100"><Spinner className="mr-1.5 h-3 w-3" /> Building your question set</StatusPill>
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">A focused interview is being prepared for you.</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-indigo-100/80 sm:text-base">DeepSeek is reviewing your selected areas and creating questions that fit your experience. This usually takes less than a minute.</p>
          </div>
        </div>
        <div className="grid gap-0 divide-y divide-slate-100 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            ["1", "Reviewing context", "Resume and role requirements"],
            ["2", "Designing questions", "Balanced for your selected time"],
            ["3", "Final checks", "Preparing the live interview room"],
          ].map(([number, title, description]) => <div key={number} className="flex gap-3 px-6 py-5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-700">{number}</span>
            <div><p className="m-0 text-sm font-semibold text-slate-900">{title}</p><p className="m-0 mt-1 text-xs leading-5 text-slate-500">{description}</p></div>
          </div>)}
        </div>
      </div>}

      {isReady && configuration && <>
        <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 px-7 py-8 text-white shadow-xl shadow-slate-200/70 sm:px-9">
          <div className="absolute right-0 top-0 h-48 w-48 -translate-y-1/3 translate-x-1/4 rounded-full bg-indigo-500/25 blur-3xl" />
          <div className="relative flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-2xl">
              <StatusPill className="mb-4 bg-emerald-400/15 text-emerald-200"><span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-300" /> Interview ready</StatusPill>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Settle in. You’re one step away.</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">Check your setup, speak naturally, and take a moment to think before answering. Your feedback will be private to your account.</p>
            </div>
            <div className="flex shrink-0 items-center gap-3 rounded-xl bg-white/[0.07] px-4 py-3 ring-1 ring-white/10">
              <SetupIcon name="clock" className="h-5 w-5 text-indigo-300" />
              <div><p className="m-0 text-xs text-slate-400">Session length</p><p className="m-0 text-sm font-semibold">{configuration.duration_minutes} minutes</p></div>
            </div>
          </div>
        </section>

        <div className="grid items-start gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-6 py-5">
              <div className="flex items-center justify-between gap-4"><div><h2 className="m-0 text-lg font-semibold text-slate-950">Device check</h2><p className="m-0 mt-1 text-sm text-slate-500">Make sure the interviewer can hear you clearly.</p></div>{allowed && <StatusPill tone="success"><SetupIcon name="check" className="mr-1 h-3.5 w-3.5" /> Ready</StatusPill>}</div>
            </div>
            <div className="space-y-5 p-6">
              <div className={`rounded-xl border p-4 transition-colors ${allowed ? "border-emerald-200 bg-emerald-50/60" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-center gap-3">
                  <span className={`grid h-10 w-10 place-items-center rounded-xl ${allowed ? "bg-emerald-100 text-emerald-700" : "bg-white text-slate-600 shadow-sm"}`}><SetupIcon name="microphone" /></span>
                  <div className="min-w-0 flex-1"><p className="m-0 text-sm font-semibold text-slate-900">{permissionLabel}</p><p className="m-0 mt-0.5 text-xs text-slate-500">{allowed ? "Permission granted — say a few words to test your level." : "Browser permission is required before starting."}</p></div>
                </div>
                {allowed && <div className="mt-4" aria-label="Microphone input level"><div className="mb-2 flex justify-between text-[0.7rem] font-medium uppercase tracking-wider text-slate-500"><span>Input level</span><span>{level > 0.03 ? "Signal detected" : "Listening…"}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-[width] duration-75" style={{width: `${Math.min(100, Math.max(3, level * 400))}%`}} /></div></div>}
              </div>

              {allowed && configuration.video_enabled && <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-950"><video className="aspect-video w-full object-cover" aria-label="Camera preview" autoPlay muted playsInline ref={element => { video.current = element; if (element) element.srcObject = stream.current; }} /><div className="flex items-center gap-2 bg-slate-900 px-3 py-2 text-xs text-slate-300"><SetupIcon name="camera" className="h-4 w-4" /> Camera preview</div></div>}

              <Button className="w-full rounded-xl py-3" variant={allowed ? "secondary" : "primary"} disabled={busy || allowed} onClick={() => void allow()}>
                {busy && !allowed ? <Spinner className="h-4 w-4" /> : allowed ? <SetupIcon name="check" className="h-4 w-4" /> : <SetupIcon name={configuration.video_enabled ? "camera" : "microphone"} className="h-4 w-4" />}
                {allowed ? "Device access confirmed" : `Allow ${permissionLabel.toLowerCase()}`}
              </Button>
            </div>
          </div>

          <div className="space-y-6">
            <Card className="rounded-2xl border-slate-200 p-6 shadow-sm">
              <h2 className="m-0 text-lg font-semibold text-slate-950">Session overview</h2>
              <dl className="mt-5 space-y-4">
                {fieldLabel && <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4"><dt className="text-sm text-slate-500">Field</dt><dd className="m-0 max-w-[65%] text-right text-sm font-medium text-slate-900">{fieldLabel}</dd></div>}
                <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4"><dt className="text-sm text-slate-500">Focus</dt><dd className="m-0 max-w-[65%] text-right text-sm font-medium text-slate-900">{focusLabel}</dd></div>
                <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-4"><dt className="text-sm text-slate-500">Format</dt><dd className="m-0 text-sm font-medium text-slate-900">{configuration.video_enabled ? "Audio + video" : "Audio only"}</dd></div>
                <div className="flex items-center justify-between gap-4"><dt className="text-sm text-slate-500">Language</dt><dd className="m-0 text-sm font-medium text-slate-900">English</dd></div>
              </dl>
            </Card>

            <label className={`block cursor-pointer rounded-2xl border p-5 transition-all ${consent ? "border-indigo-300 bg-indigo-50/70 ring-2 ring-indigo-100" : "border-slate-200 bg-white hover:border-indigo-200"}`}>
              <span className="flex items-start gap-3"><input className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span><span className="flex items-center gap-2 text-sm font-semibold text-slate-900"><SetupIcon name="shield" className="h-4 w-4 text-indigo-600" /> Private practice consent</span><span className="mt-1.5 block text-xs leading-5 text-slate-500">I consent to recording and AI feedback for my private practice report.</span></span></span>
            </label>

            <Button className="w-full rounded-xl py-3.5 text-base shadow-lg shadow-indigo-200/70" disabled={busy || !allowed || !consent} onClick={() => void begin()}>
              {busy ? <><Spinner className="h-4 w-4" /> Opening interview room…</> : <>Begin interview <span aria-hidden="true">→</span></>}
            </Button>
            {(!allowed || !consent) && <p className="m-0 text-center text-xs text-slate-500">Complete the device check and consent to continue.</p>}
          </div>
        </div>
      </>}

      {error && interview && ["preparing", "failed"].includes(interview.state) && <div className="flex flex-wrap items-center gap-3"><Button disabled={busy} onClick={() => void retryPlan()}>{busy ? <><Spinner className="h-4 w-4" /> Retrying…</> : "Retry preparation"}</Button><Link className="text-sm font-medium text-slate-600 hover:text-indigo-700" to={draft?.language ? "/practice/language/new" : "/practice/new"}>Change interview settings</Link></div>}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5 text-sm"><Link className="font-medium text-slate-600 hover:text-indigo-700 sm:hidden" to="/mock-interviews">← My interviews</Link><Link className="ml-auto text-slate-500 hover:text-indigo-700" to="/privacy-notice">Privacy and data use</Link></footer>
    </div>
  </PageShell>;
}
