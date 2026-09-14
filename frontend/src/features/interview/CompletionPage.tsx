import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";

export function CompletionPage() {
  const { interviewId } = useParams<{ interviewId: string }>();
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 px-6 py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">
        Thanks for completing your interview
      </h1>
      <p className="text-sm leading-relaxed text-ink-700">
        Your responses are being scored. Your personalised report will highlight strengths,
        improvement areas, and topic feedback.
      </p>
      <Link to={`/mock-interviews/${interviewId}/report`} className="mx-auto">
        <Button>View my report</Button>
      </Link>
    </div>
  );
}
