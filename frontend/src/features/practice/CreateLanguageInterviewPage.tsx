import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Select } from "../../components/ui/Field";
import { PageShell } from "../../components/ui/PageShell";
import { savePendingInterview } from "../../lib/pendingInterview";
import type { InterviewDraft, InterviewLanguage, InterviewLevel } from "../../lib/types";

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
  const navigate = useNavigate();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const draft: InterviewDraft = {
      resume_id: null,
      field_type: null,
      job_description: null,
      topics: null,
      language,
      level,
      duration_minutes: duration,
      video_enabled: videoEnabled,
    };
    savePendingInterview(draft);
    navigate("/practice/preflight", {state: {draft, activeSection: "language"}});
  };

  return <PageShell title="Practice a language interview">
    <form onSubmit={submit} className="flex max-w-md flex-col gap-6">
      <Field label="Language"><Select value={language} onChange={(e) => setLanguage(e.target.value as InterviewLanguage)}>{LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}</Select></Field>
      <Field label="Type"><Select value={level} onChange={(e) => setLevel(e.target.value as InterviewLevel)}>{LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}</Select></Field>
      <p className="text-sm text-ink-500">The interview and speech recognition use English.</p>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Interview length"><Select value={duration} onChange={(e) => setDuration(Number(e.target.value) as 15 | 30)}><option value={15}>15 minutes</option><option value={30}>30 minutes</option></Select></Field><Card className="flex items-center gap-3"><input id="video" type="checkbox" checked={videoEnabled} onChange={(e) => setVideoEnabled(e.target.checked)} /><label htmlFor="video" className="text-sm text-ink-700">Record camera video</label></Card></div>
      <Button type="submit">Continue to device check</Button>
      <p className="text-sm text-ink-500">Have a resume and job description instead? <Link className="underline" to="/practice/new">Create a tailored interview</Link>.</p>
    </form>
  </PageShell>;
}
