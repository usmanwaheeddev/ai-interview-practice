import {useEffect, useState} from "react";
import {Link} from "react-router-dom";
import {PageShell} from "../../components/ui/PageShell";
import {apiRequest} from "../../lib/api";
import type {MockInterview} from "../../lib/types";
export function InterviewHistoryPage() {
  const [items,setItems]=useState<MockInterview[]>([]);
  const [error,setError]=useState("");
  useEffect(()=>{void apiRequest<MockInterview[]>("/mock-interviews").then(setItems).catch(()=>setError("Could not load interviews."));},[]);
  return <PageShell title="My mock interviews"><div className="flex gap-4"><Link to="/practice/new">New mock interview</Link><Link to="/practice/language/new">New language interview</Link></div>{error && <p role="alert">{error}</p>}
    {!items.length && !error && <p>Create an interview to begin practising.</p>}
    {items.map(i=><Link className="rounded border p-4" key={i.id} to={`/mock-interviews/${i.id}/${["completed","scoring","scored"].includes(i.state) ? "report" : "preflight"}`}>
      {i.topics.length ? i.topics.join(", ").replaceAll("_"," ") : `${i.language} · ${i.level}`} · {i.duration_minutes} minutes · {i.state.replaceAll("_"," ")}
    </Link>)}</PageShell>;
}
