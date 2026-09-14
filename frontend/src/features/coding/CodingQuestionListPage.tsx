import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest, ApiError } from "../../lib/api";
import type { CodingQuestionListItem } from "../../lib/types";

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

const DIFFICULTY_CLASSES: Record<string, string> = {
  easy: "bg-success-50 text-success-700",
  medium: "bg-warning-50 text-warning-700",
  hard: "bg-danger-50 text-danger-700",
};

export function CodingQuestionListPage() {
  const [questions, setQuestions] = useState<CodingQuestionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<CodingQuestionListItem[]>("/coding-questions")
      .then(setQuestions)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load questions"));
  }, []);

  return (
    <PageShell title="Coding challenges">
      {error && <Alert>{error}</Alert>}
      {!questions && !error && <p className="text-sm text-ink-500">Loading…</p>}
      <div className="flex flex-col gap-3">
        {questions?.map((q) => (
          <Link key={q.id} to={`/coding/${q.slug}`}>
            <Card className="flex items-center justify-between transition-shadow hover:shadow-md">
              <span className="font-medium text-ink-900">{q.title}</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${DIFFICULTY_CLASSES[q.difficulty] ?? ""}`}
              >
                {DIFFICULTY_LABELS[q.difficulty] ?? q.difficulty}
              </span>
            </Card>
          </Link>
        ))}
      </div>
    </PageShell>
  );
}
