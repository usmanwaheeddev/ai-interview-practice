import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Select, Textarea } from "../../components/ui/Field";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest, apiUpload, ApiError } from "../../lib/api";
import type { MockInterview, PracticeTopic, Resume } from "../../lib/types";

const TOPICS: { value: PracticeTopic; label: string }[] = [
  { value: "all_areas", label: "All areas" },
  { value: "system_design", label: "System design" },
  { value: "programming", label: "Programming language & technical depth" },
  { value: "problem_solving", label: "Problem solving / DSA" },
  { value: "behavioral", label: "Behavioral" },
  { value: "database", label: "Database" },
  { value: "architecture", label: "Architecture" },
];

export function CreatePracticeInterviewPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [resumeId, setResumeId] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [topics, setTopics] = useState<PracticeTopic[]>(["all_areas"]);
  const [duration, setDuration] = useState<15 | 30>(15);
  const [videoEnabled, setVideoEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    apiRequest<Resume[]>("/resumes")
      .then((data) => { setResumes(data); setResumeId(data[0]?.id ?? ""); })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load resumes"));
  }, []);

  const toggleTopic = (topic: PracticeTopic) => {
    if (topic === "all_areas") return setTopics(["all_areas"]);
    setTopics((current) => {
      const withoutAll = current.filter((item) => item !== "all_areas");
      const next = withoutAll.includes(topic) ? withoutAll.filter((item) => item !== topic) : [...withoutAll, topic];
      return next.length ? next : ["all_areas"];
    });
  };

  const uploadResume = async (file: File) => {
    const accepted = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
    if (!accepted.includes(file.type)) {
      setError("Please upload a PDF or DOCX resume.");
      return;
    }
    setBusy(true); setError(null);
    try {
      const resume = await apiUpload<Resume>("/resumes", file);
      setResumes((current) => [resume, ...current]);
      setResumeId(resume.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload resume");
    } finally { setBusy(false); }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const practice = await apiRequest<MockInterview>("/mock-interviews", {
        method: "POST",
        body: {
          job_description: jobDescription.trim() || null,
          resume_id: resumeId,
          topics,
          duration_minutes: duration,
          video_enabled: videoEnabled,
        },
      });
      navigate(`/mock-interviews/${practice.id}/preflight`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not prepare mock interview");
    } finally { setBusy(false); }
  };

  return <PageShell title="Create mock interview">
    <form onSubmit={submit} className="flex max-w-2xl flex-col gap-6">
      <Field label="Job description" hint="Optional — the interview can be based entirely on your resume."><Textarea rows={8} value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} placeholder="Optional: paste the role description, responsibilities, and requirements…" /></Field>
      <Field label="Resume" hint={!resumes.length ? "A resume is required — upload one below to enable interview creation." : undefined}><div className="flex flex-col gap-3"><Select required value={resumeId} onChange={(e) => setResumeId(e.target.value)} disabled={!resumes.length}><option value="">{resumes.length ? "Choose an uploaded resume" : "Upload a resume below"}</option>{resumes.map((resume) => <option key={resume.id} value={resume.id}>{resume.filename}</option>)}</Select><label className="text-sm text-ink-700">Upload a resume (PDF or DOCX)<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(e) => { const file = e.target.files?.[0]; if (file) void uploadResume(file); }} className="mt-1 block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-ink-100 file:px-3 file:py-1.5 file:text-sm file:font-medium" /></label></div></Field>
      <fieldset><legend className="text-sm font-medium text-ink-700">What would you like to practise?</legend><div className="mt-2 grid gap-2 sm:grid-cols-2">{TOPICS.map((topic) => <label key={topic.value} className="flex gap-2 rounded border border-ink-300/70 p-3 text-sm"><input type="checkbox" checked={topics.includes(topic.value)} onChange={() => toggleTopic(topic.value)} />{topic.label}</label>)}</div></fieldset>
      <p className="text-sm text-ink-500">The interview and speech recognition use English.</p>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Interview length"><Select value={duration} onChange={(e) => setDuration(Number(e.target.value) as 15 | 30)}><option value={15}>15 minutes</option><option value={30}>30 minutes</option></Select></Field><Card className="flex items-center gap-3"><input id="video" type="checkbox" checked={videoEnabled} onChange={(e) => setVideoEnabled(e.target.checked)} /><label htmlFor="video" className="text-sm text-ink-700">Record camera video</label></Card></div>
      {error && <Alert>{error}</Alert>}
      {!busy && !resumeId && <p className="text-sm text-red-600">Upload a resume above before creating an interview.</p>}
      <Button type="submit" disabled={busy || !resumeId}>{busy ? "Preparing…" : "Create interview"}</Button>
      <p className="text-sm text-ink-500">Want to drill a specific language instead? <Link className="underline" to="/practice/language/new">Practice a language interview</Link>.</p>
    </form>
  </PageShell>;
}
