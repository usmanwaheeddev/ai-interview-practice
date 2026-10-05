import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest } from "../../lib/api";
import type { InterviewState, MockInterview } from "../../lib/types";
import {areaLabel, INTERVIEW_FIELDS} from "../../lib/interviewFields";

const completedStates: InterviewState[] = ["completed", "scoring", "scored"];

const statusStyles: Record<InterviewState, string> = {
  preparing: "bg-amber-50 text-amber-700 ring-amber-600/20",
  ready: "bg-blue-50 text-blue-700 ring-blue-600/20",
  in_progress: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
  disconnected: "bg-orange-50 text-orange-700 ring-orange-600/20",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  scoring: "bg-violet-50 text-violet-700 ring-violet-600/20",
  scored: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  failed: "bg-red-50 text-red-700 ring-red-600/20",
};

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function interviewTitle(interview: MockInterview) {
  if (interview.topics.length) {
    const areas = interview.topics.map(areaLabel).join(", ");
    return interview.field_type ? `${INTERVIEW_FIELDS[interview.field_type].label} · ${areas}` : areas;
  }
  return `${interview.language ? humanize(interview.language) : "Language"} · ${interview.level ? humanize(interview.level) : "Practice"}`;
}

export function InterviewHistoryPage() {
  const [items, setItems] = useState<MockInterview[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void apiRequest<MockInterview[]>("/mock-interviews").then(setItems).catch(() => setError("Could not load interviews."));
  }, []);

  const actions = <div className="flex items-center gap-2">
    <Link className="hidden rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 sm:inline-flex" to="/practice/language/new">Language interview</Link>
    <Link className="inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700" to="/practice/new">New interview</Link>
  </div>;

  return <PageShell title="My mock interviews" actions={actions}>
    {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">{error}</div>}
    {!items.length && !error && <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      <h2 className="text-lg font-semibold text-slate-900">No interviews yet</h2>
      <p className="mt-2 text-sm text-slate-500">Create an interview to begin practising.</p>
      <Link className="mt-6 inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white" to="/practice/new">Create interview</Link>
    </div>}
    {items.length > 0 && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((interview) => {
        const destination = completedStates.includes(interview.state) ? "report" : "preflight";
        const date = new Intl.DateTimeFormat(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "numeric",
          minute: "2-digit",
        }).format(new Date(interview.created_at));
        return <Link
          className="group flex min-h-44 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          key={interview.id}
          to={`/mock-interviews/${interview.id}/${destination}`}
        >
          <div className="flex items-start justify-between gap-3">
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${statusStyles[interview.state]}`}>{humanize(interview.state)}</span>
            <time className="whitespace-nowrap text-right text-xs text-slate-400" dateTime={interview.created_at}>{date}</time>
          </div>
          <h2 className="mt-5 line-clamp-2 text-base font-semibold capitalize leading-6 text-slate-900">{interviewTitle(interview)}</h2>
          <div className="mt-auto flex items-end justify-between gap-4 pt-5">
            <p className="text-sm text-slate-500">{interview.duration_minutes} minutes · {interview.spoken_language.toUpperCase()}</p>
            <span className="text-sm font-semibold text-indigo-600 transition-transform group-hover:translate-x-0.5" aria-hidden="true">View →</span>
          </div>
        </Link>;
      })}
    </div>}
  </PageShell>;
}
