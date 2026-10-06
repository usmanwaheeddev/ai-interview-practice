import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { Card } from "../../components/ui/Card";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest, ApiError } from "../../lib/api";
import type { InterviewReport } from "../../lib/types";

export function PracticeReportPage() {
  const {interviewId} = useParams();
  const [report,setReport] = useState<InterviewReport | null>(null);
  const [error,setError] = useState<string | null>(null);
  const [version,setVersion] = useState(0);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const result = await apiRequest<InterviewReport>(`/mock-interviews/${interviewId}/report`);
        if (cancelled) return;
        setReport(result);
        if (result.state === "scoring") timer = setTimeout(() => void load(), 3000);
      } catch(err) { if(!cancelled) setError(err instanceof ApiError ? err.message : "Could not load report."); }
    };
    void load();
    return () => {cancelled=true; clearTimeout(timer);};
  }, [interviewId,version]);
  const rescore = async () => {
    try {
      await apiRequest(`/mock-interviews/${interviewId}/rescore`,{method:"POST"});
      setVersion(v=>v+1); setError(null);
    } catch(err) {setError(err instanceof ApiError ? err.message : "Retry failed.");}
  };
  const hasScore = report?.overall_score != null && report.score_status !== "failed" && report.score_status !== "pending";
  return <PageShell title="Your interview report">
    {error && <Alert>{error}</Alert>}
    {!report && !error && <p>Loading…</p>}
    {report?.state === "scoring" && <p>Preparing your feedback…</p>}
    {report?.failure_reason && <Alert>{report.failure_reason}</Alert>}
    {report && ["completed","scored"].includes(report.state) && <Button onClick={()=>void rescore()}>Retry scoring</Button>}
    {hasScore && report && <>
      <Card><p className="text-3xl font-semibold">{report.overall_score}/5</p><p>{report.readiness?.replaceAll("_"," ")}</p></Card>
      {report.score_status === "needs_review" && <Alert>Some evidence could not be verified. Treat these scores as provisional.</Alert>}
      <h2 className="text-lg font-semibold">Strengths</h2>
      {report.strengths.length ? report.strengths.map(x=><p key={x}>{x}</p>) : <p>No high-scoring strengths identified in this session.</p>}
      <h2 className="text-lg font-semibold">Areas to improve</h2>
      {report.weaknesses.length ? report.weaknesses.map(x=><p key={x}>{x}</p>) : <p>No major gaps identified in the assessed topics.</p>}
      <h2 className="text-lg font-semibold">Next practice steps</h2>
      {report.improvements.map(x=><p key={x}>{x}</p>)}
      {report.dimensions.map(d=><Card key={d.topic}><strong>{d.topic} — {d.score}/5</strong><p>{d.feedback}</p>{d.evidence.map((e,i)=><blockquote key={i}>{e}</blockquote>)}</Card>)}
    </>}
    {!!report?.transcript.length && <><h2 className="text-lg font-semibold">Transcript</h2>{report.transcript.map(t=><p key={t.turn_index}><strong>{t.speaker === "agent" ? "Interviewer" : "You"}:</strong> {t.text}</p>)}</>}
    {report && <section className="mt-8 space-y-4" aria-labelledby="recordings-heading">
      <div>
        <h2 id="recordings-heading" className="text-lg font-semibold">Interview recordings</h2>
        <p className="mt-1 text-sm text-slate-600">Play each captured segment in order. Video interviews include your camera recording; audio interviews include your microphone recording.</p>
      </div>
      {report.recordings.length ? <div className="grid gap-4">
        {report.recordings.map(r=><Card key={r.chunk_index}>
          {r.kind === "video"
            ? <><p className="mb-3 text-sm font-semibold text-slate-800">Video segment {r.chunk_index + 1}</p><video className="w-full max-w-3xl rounded-lg bg-black" src={r.url} controls playsInline preload="metadata" aria-label={`Video recording segment ${r.chunk_index + 1}`} /></>
            : <div className="rounded-xl border border-indigo-100 bg-gradient-to-r from-indigo-50 via-white to-violet-50 p-4 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-lg text-white" aria-hidden="true">♫</span>
                    <div><p className="m-0 text-sm font-semibold text-slate-900">Your answer</p><p className="m-0 text-xs text-slate-500">Audio segment {r.chunk_index + 1}</p></div>
                  </div>
                  <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200">WAV recording</span>
                </div>
                <div className="flex h-8 items-center gap-1.5" aria-hidden="true">
                  {[8, 17, 12, 25, 16, 30, 20, 14, 27, 11, 22, 16, 29, 13, 19, 9].map((height, index) => <span key={index} className="w-1.5 rounded-full bg-indigo-300" style={{height}} />)}
                </div>
                <audio className="mt-3 w-full accent-indigo-600" src={r.url} controls preload="metadata" aria-label={`Audio recording segment ${r.chunk_index + 1}`} />
              </div>}
        </Card>)}
      </div> : <p className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">No recording segments are available for this interview.</p>}
    </section>}
    <nav className="mt-8 flex flex-wrap gap-3 border-t border-slate-200 pt-6" aria-label="Report navigation">
      <Link className="inline-flex min-h-11 items-center rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700" to="/practice/new">Start another mock interview</Link>
      <Link className="inline-flex min-h-11 items-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50" to="/mock-interviews">My interviews</Link>
    </nav>
  </PageShell>;
}
