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
export type PracticeField = "computer_science" | "physics" | "mathematics" | "business";
export type PracticeTopic =
  | "system_design" | "programming" | "problem_solving" | "behavioral" | "database" | "architecture"
  | "mechanics" | "electromagnetism" | "thermodynamics" | "quantum_physics" | "optics" | "relativity"
  | "algebra" | "calculus" | "probability_statistics" | "discrete_mathematics" | "linear_algebra" | "numerical_methods"
  | "strategy" | "finance" | "marketing" | "operations" | "leadership" | "economics";
export type PracticeAreaSelection = PracticeTopic | "all_areas";
export type InterviewLanguage = "python" | "java" | "csharp";
export type InterviewLevel = "basic" | "advanced" | "practical";
export type SpokenLanguage = "en" | "hi" | "ur";
export interface InterviewDraft {
  resume_id: string | null;
  field_type: PracticeField | null;
  job_description: string | null;
  topics: PracticeAreaSelection[] | null;
  language: InterviewLanguage | null;
  level: InterviewLevel | null;
  duration_minutes: 15 | 30;
  video_enabled: boolean;
}
export type InterviewState = "preparing" | "ready" | "in_progress" | "disconnected" | "completed" | "scoring" | "scored" | "failed";
export interface MockInterview {
  id: string;
  resume_id: string | null;
  field_type: PracticeField | null;
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
