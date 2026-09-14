export type ParseStatus = "pending" | "complete" | "failed";
export interface Resume {
  id: string;
  filename: string;
  mime_type: string;
  parse_status: ParseStatus;
  parsed: Record<string, unknown>;
  parsed_at: string | null;
  created_at: string;
}
export type PracticeTopic = "all_areas" | "system_design" | "programming" | "problem_solving" | "behavioral" | "database" | "architecture";
export type InterviewLanguage = "python" | "java" | "csharp";
export type InterviewLevel = "basic" | "advanced" | "practical";
export type SpokenLanguage = "en" | "hi" | "ur";
export type InterviewState = "preparing" | "ready" | "in_progress" | "disconnected" | "completed" | "scoring" | "scored" | "failed";
export interface MockInterview {
  id: string;
  resume_id: string | null;
  topics: PracticeTopic[];
  language: InterviewLanguage | null;
  level: InterviewLevel | null;
  spoken_language: SpokenLanguage;
  duration_minutes: 15 | 30;
  video_enabled: boolean;
  state: InterviewState;
  elapsed_s: number;
  remaining_s: number;
  failure_reason: string | null;
  created_at: string;
}
export type MediaKind = "audio" | "video";
export interface InterviewReport {
  state: InterviewState;
  score_status: "pending" | "complete" | "needs_review" | "failed" | null;
  overall_score: string | null;
  readiness: string | null;
  failure_reason: string | null;
  strengths: string[];
  weaknesses: string[];
  improvements: string[];
  dimensions: {topic: string; score: number; feedback: string; evidence: string[]; evidence_verified: boolean}[];
  transcript: {speaker: "agent" | "user"; text: string; turn_index: number}[];
  recordings: {kind: MediaKind; chunk_index: number; url: string}[];
}

export type CodingDifficulty = "easy" | "medium" | "hard";
export type CodingLanguage = "python" | "csharp" | "java";
export type CodingSubmissionStatus = "pending" | "running" | "passed" | "failed" | "error";

export interface CodingQuestionListItem {
  id: string;
  slug: string;
  title: string;
  difficulty: CodingDifficulty;
}

export interface CodingExample {
  input_display: string;
  output_display: string;
  explanation: string | null;
}

export interface CodingQuestionDetail {
  slug: string;
  title: string;
  difficulty: CodingDifficulty;
  description: string;
  constraints: string[];
  examples: CodingExample[];
  starter_code: Record<CodingLanguage, string>;
}

export interface CodingTestCaseResult {
  test_case_id: string;
  is_sample: boolean;
  passed: boolean;
  runtime_ms: number;
  actual_output: unknown;
  expected_output: unknown;
  stderr: string | null;
}

export interface CodingSubmissionResult {
  id: string;
  status: CodingSubmissionStatus;
  error_message: string | null;
  results: CodingTestCaseResult[];
}

export interface CodingHintLogItem {
  created_at: string;
  code_before: string;
  hint_line: string;
  cursor_line: number | null;
  cursor_column: number | null;
}

export interface CodingReviewLogItem {
  created_at: string;
  code_reviewed: string;
  review_text: string;
  contained_code: boolean;
}

export interface CodingAiUsage {
  hints_used: number;
  hint_limit: number;
  hints: CodingHintLogItem[];
  reviews: CodingReviewLogItem[];
}
