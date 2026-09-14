import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Select } from "../../components/ui/Field";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest, ApiError } from "../../lib/api";
import type { InterviewLanguage, InterviewLevel, MockInterview } from "../../lib/types";

const LANGUAGES: { value: InterviewLanguage; label: string }[] = [
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
  { value: "csharp", label: "C#" },
];

const LEVELS: { value: InterviewLevel; label: string }[] = [
  { value: "basic", label: "Basic" },
  { value: "advanced", label: "Advanced" },
  { value: "practical", label: "Practical" },
];

export function CreateLanguageInterviewPage() {
  const [language, setLanguage] = useState<InterviewLanguage>("python");
  const [level, setLevel] = useState<InterviewLevel>("basic");
  const [duration, setDuration] = useState<15 | 30>(15);
  const [videoEnabled, setVideoEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const practice = await apiRequest<MockInterview>("/mock-interviews", {
        method: "POST",
        body: {
          language,
          level,
          duration_minutes: duration,
          video_enabled: videoEnabled,
        },
      });
      navigate(`/mock-interviews/${practice.id}/preflight`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not prepare interview");
    } finally { setBusy(false); }
  };

  return <PageShell title="Practice a language interview">
    <form onSubmit={submit} className="flex max-w-md flex-col gap-6">
      <Field label="Language"><Select value={language} onChange={(e) => setLanguage(e.target.value as InterviewLanguage)}>{LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}</Select></Field>
      <Field label="Type"><Select value={level} onChange={(e) => setLevel(e.target.value as InterviewLevel)}>{LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}</Select></Field>
      <p className="text-sm text-ink-500">The interview and speech recognition use English.</p>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Interview length"><Select value={duration} onChange={(e) => setDuration(Number(e.target.value) as 15 | 30)}><option value={15}>15 minutes</option><option value={30}>30 minutes</option></Select></Field><Card className="flex items-center gap-3"><input id="video" type="checkbox" checked={videoEnabled} onChange={(e) => setVideoEnabled(e.target.checked)} /><label htmlFor="video" className="text-sm text-ink-700">Record camera video</label></Card></div>
      {error && <Alert>{error}</Alert>}
      <Button type="submit" disabled={busy}>{busy ? "Preparing…" : "Create interview"}</Button>
      <p className="text-sm text-ink-500">Have a resume and job description instead? <Link className="underline" to="/practice/new">Create a tailored interview</Link>.</p>
    </form>
  </PageShell>;
}
