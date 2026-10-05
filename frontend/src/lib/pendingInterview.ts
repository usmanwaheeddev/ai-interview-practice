import type { InterviewDraft } from "./types";
import { ALL_PRACTICE_TOPICS, INTERVIEW_FIELDS } from "./interviewFields";

const STORAGE_KEY = "pending-interview-draft";

interface PendingInterviewState {
  draft: InterviewDraft;
  createdInterviewId?: string;
}

const interviewLanguages = new Set(["python", "java", "csharp"]);
const interviewLevels = new Set(["basic", "advanced", "practical"]);

function isDraft(value: unknown): value is InterviewDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as Partial<InterviewDraft>;
  if (![15, 30].includes(draft.duration_minutes ?? 0) || typeof draft.video_enabled !== "boolean") {
    return false;
  }

  const resumeMode =
    typeof draft.resume_id === "string" &&
    draft.resume_id.length > 0 &&
    (draft.job_description === null || typeof draft.job_description === "string") &&
    Array.isArray(draft.topics) &&
    draft.topics.length > 0 &&
    typeof draft.field_type === "string" &&
    draft.field_type in INTERVIEW_FIELDS &&
    draft.topics.every(topic => topic === "all_areas" || ALL_PRACTICE_TOPICS.has(topic)) &&
    ((draft.topics.length === 1 && draft.topics[0] === "all_areas") || draft.topics.every(topic =>
      INTERVIEW_FIELDS[draft.field_type as keyof typeof INTERVIEW_FIELDS].areas.some(area => area.value === topic)
    )) &&
    draft.language === null &&
    draft.level === null;
  const languageMode =
    draft.resume_id === null &&
    draft.field_type === null &&
    draft.job_description === null &&
    draft.topics === null &&
    typeof draft.language === "string" &&
    interviewLanguages.has(draft.language) &&
    typeof draft.level === "string" &&
    interviewLevels.has(draft.level);

  return resumeMode !== languageMode;
}

function loadState(): PendingInterviewState | null {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null");
    if (!value || typeof value !== "object") return null;

    // Accept drafts written by the previous format so an in-progress browser
    // tab survives an application update.
    if (isDraft(value)) return {draft: value};

    const state = value as Partial<PendingInterviewState>;
    if (!isDraft(state.draft)) return null;
    if (state.createdInterviewId !== undefined && typeof state.createdInterviewId !== "string") {
      return null;
    }
    return state as PendingInterviewState;
  } catch {
    return null;
  }
}

export function savePendingInterview(draft: InterviewDraft) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({draft} satisfies PendingInterviewState));
}

export function loadPendingInterview(): InterviewDraft | null {
  return loadState()?.draft ?? null;
}

export function savePendingInterviewId(id: string) {
  const state = loadState();
  if (!state) return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({...state, createdInterviewId: id}));
}

export function loadPendingInterviewId(): string | null {
  return loadState()?.createdInterviewId ?? null;
}

export function clearPendingInterview() {
  sessionStorage.removeItem(STORAGE_KEY);
}
