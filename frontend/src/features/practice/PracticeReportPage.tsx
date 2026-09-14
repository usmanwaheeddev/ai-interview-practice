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
    {!!report?.recordings.length && <><h2>Recordings</h2><p>Recorded segments, in order.</p>{report.recordings.map(r=>r.kind==="video" ? <video key={r.chunk_index} src={r.url} controls /> : <audio key={r.chunk_index} src={r.url} controls />)}</>}
    <Link to="/practice/new">Start another mock interview →</Link><Link to="/mock-interviews">My interviews</Link>
  </PageShell>;
}
