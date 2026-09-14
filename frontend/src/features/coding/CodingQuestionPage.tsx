import Editor, { type OnMount } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest, ApiError, streamSse } from "../../lib/api";
import type {
  CodingAiUsage,
  CodingLanguage,
  CodingQuestionDetail,
  CodingSubmissionResult,
} from "../../lib/types";

const LANGUAGES: { value: CodingLanguage; label: string; monacoId: string }[] = [
  { value: "python", label: "Python", monacoId: "python" },
  { value: "csharp", label: "C#", monacoId: "csharp" },
  { value: "java", label: "Java", monacoId: "java" },
];

const DIFFICULTY_LABELS: Record<string, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

export function CodingQuestionPage() {
  const { slug } = useParams<{ slug: string }>();
  const [question, setQuestion] = useState<CodingQuestionDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [language, setLanguage] = useState<CodingLanguage>("python");
  // Each language keeps its own in-progress code so switching tabs never
  // discards work — keyed by language, initialized from starter_code once
  // the question loads.
  const [codeByLanguage, setCodeByLanguage] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<CodingSubmissionResult | null>(null);

  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewText, setReviewText] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [hintsUsed, setHintsUsed] = useState<number | null>(null);
  const [hintLimit, setHintLimit] = useState<number | null>(null);
  const [hintLoading, setHintLoading] = useState(false);
  const [hintError, setHintError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    apiRequest<CodingQuestionDetail>(`/coding-questions/${slug}`)
      .then((detail) => {
        setQuestion(detail);
        setCodeByLanguage(detail.starter_code);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Could not load question"));
    apiRequest<CodingAiUsage>(`/coding-questions/${slug}/ai-usage`)
      .then((usage) => {
        setHintsUsed(usage.hints_used);
        setHintLimit(usage.hint_limit);
      })
      .catch(() => {
        // Non-critical — the Hint button still works; the backend is the
        // real source of truth for the limit either way.
      });
  }, [slug]);

  const handleEditorMount: OnMount = (editor) => {
    editorRef.current = editor;
  };

  const requestReview = async () => {
    if (!slug) return;
    setReviewOpen(true);
    setReviewText("");
    setReviewError(null);
    setReviewLoading(true);
    try {
      await streamSse(
        `/coding-questions/${slug}/review`,
        { language, code: codeByLanguage[language] ?? "" },
        { onMessage: (chunk) => setReviewText((prev) => prev + chunk) },
      );
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.message : "Could not get AI review");
    } finally {
      setReviewLoading(false);
    }
  };

  const requestHint = async () => {
    const editor = editorRef.current;
    if (!slug || !editor) return;
    const position = editor.getPosition();
    const model = editor.getModel();
    const insertLine = position?.lineNumber ?? 1;
    let insertColumn = position?.column ?? 1;

    setHintLoading(true);
    setHintError(null);
    try {
      await streamSse(
        `/coding-questions/${slug}/hint`,
        {
          language,
          code: codeByLanguage[language] ?? "",
          cursor_line: position?.lineNumber,
          cursor_column: position?.column,
        },
        {
          onMessage: (chunk) => {
            if (!model) return;
            // Progressive insert at the advancing cursor position, so it
            // reads as the line being typed in rather than appearing whole.
            editor.executeEdits("ai-hint", [
              {
                range: {
                  startLineNumber: insertLine,
                  startColumn: insertColumn,
                  endLineNumber: insertLine,
                  endColumn: insertColumn,
                },
                text: chunk,
                forceMoveMarkers: true,
              },
            ]);
            insertColumn += chunk.length;
            setCodeByLanguage((prev) => ({ ...prev, [language]: model.getValue() }));
          },
          onDone: (data) => {
            const parsed = JSON.parse(data) as { hints_used: number; hint_limit: number };
            setHintsUsed(parsed.hints_used);
            setHintLimit(parsed.hint_limit);
          },
        },
      );
    } catch (err) {
      setHintError(err instanceof ApiError ? err.message : "Could not get AI hint");
    } finally {
      setHintLoading(false);
    }
  };

  const hintExhausted = hintsUsed !== null && hintLimit !== null && hintsUsed >= hintLimit;

  const submit = async () => {
    if (!slug) return;
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    try {
      const submission = await apiRequest<CodingSubmissionResult>(
        `/coding-questions/${slug}/submit`,
        { method: "POST", body: { language, code: codeByLanguage[language] ?? "" } },
      );
      setResult(submission);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Could not run submission");
    } finally {
      setSubmitting(false);
    }
  };

  if (loadError) {
    return (
      <PageShell title="Coding challenge">
        <Alert>{loadError}</Alert>
      </PageShell>
    );
  }
  if (!question) {
    return (
      <PageShell title="Coding challenge">
        <p className="text-sm text-ink-500">Loading…</p>
      </PageShell>
    );
  }

  const activeMonacoLanguage = LANGUAGES.find((l) => l.value === language)?.monacoId ?? "python";

  return (
    <PageShell title={question.title}>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span className="rounded bg-ink-100 px-2 py-0.5 text-xs font-medium text-ink-700">
              {DIFFICULTY_LABELS[question.difficulty] ?? question.difficulty}
            </span>
          </div>
          <p className="whitespace-pre-line text-sm text-ink-700">{question.description}</p>

          {question.constraints.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-ink-900">Constraints</h3>
              <ul className="list-inside list-disc text-sm text-ink-700">
                {question.constraints.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {question.examples.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-ink-900">Examples</h3>
              {question.examples.map((ex, i) => (
                <div key={i} className="rounded bg-ink-100 p-3 font-mono text-xs text-ink-700">
                  <p>Input: {ex.input_display}</p>
                  <p>Output: {ex.output_display}</p>
                  {ex.explanation && <p className="mt-1 font-sans text-ink-500">{ex.explanation}</p>}
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex gap-1">
              {LANGUAGES.map((l) => (
                <button
                  key={l.value}
                  type="button"
                  onClick={() => setLanguage(l.value)}
                  className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                    language === l.value
                      ? "bg-brand-600 text-white"
                      : "bg-ink-100 text-ink-700 hover:bg-ink-300"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2" data-testid="coding-toolbar-extension-point">
              <Button variant="secondary" onClick={() => void requestReview()} disabled={reviewLoading}>
                {reviewLoading ? "Reviewing…" : "Review"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => void requestHint()}
                disabled={hintLoading || hintExhausted}
              >
                {hintExhausted
                  ? "No hints left"
                  : hintLoading
                    ? "Thinking…"
                    : `Hint${hintLimit !== null ? ` (${hintsUsed ?? 0}/${hintLimit} used)` : ""}`}
              </Button>
            </div>
          </div>

          {reviewOpen && (
            <Card className="flex flex-col gap-2">
              <p className="text-sm font-semibold text-ink-900">AI review</p>
              {reviewError ? (
                <Alert>{reviewError}</Alert>
              ) : (
                <p className="whitespace-pre-line text-sm text-ink-700">
                  {reviewText || (reviewLoading ? "Thinking…" : "")}
                </p>
              )}
            </Card>
          )}

          <Card className="p-0">
            <Editor
              height="420px"
              language={activeMonacoLanguage}
              value={codeByLanguage[language] ?? ""}
              onChange={(value) =>
                setCodeByLanguage((prev) => ({ ...prev, [language]: value ?? "" }))
              }
              onMount={handleEditorMount}
              options={{ minimap: { enabled: false }, fontSize: 13 }}
            />
          </Card>

          {hintError && <Alert>{hintError}</Alert>}

          <Button onClick={() => void submit()} disabled={submitting}>
            {submitting ? "Running…" : "Submit"}
          </Button>
          {submitError && <Alert>{submitError}</Alert>}

          {result && (
            <Card className="flex flex-col gap-3">
              <p className="text-sm font-semibold text-ink-900">
                Result: <span className="uppercase">{result.status}</span>
              </p>
              {result.error_message && <Alert>{result.error_message}</Alert>}
              <div className="flex flex-col gap-2">
                {result.results.map((r) => (
                  <div
                    key={r.test_case_id}
                    className={`rounded border p-2 text-xs ${
                      r.passed ? "border-success-600/30 bg-success-50" : "border-danger-600/30 bg-danger-50"
                    }`}
                  >
                    <p className="font-medium">
                      {r.passed ? "Passed" : "Failed"}
                      {r.is_sample ? "" : " (hidden case)"} — {r.runtime_ms}ms
                    </p>
                    {r.is_sample && (
                      <div className="mt-1 font-mono">
                        <p>Expected: {JSON.stringify(r.expected_output)}</p>
                        <p>Actual: {JSON.stringify(r.actual_output)}</p>
                        {r.stderr && <p className="text-danger-700">{r.stderr}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageShell>
  );
}
