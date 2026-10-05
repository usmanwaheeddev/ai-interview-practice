import {beforeEach, describe, expect, it} from "vitest";
import type {InterviewDraft} from "./types";
import {
  clearPendingInterview,
  loadPendingInterview,
  loadPendingInterviewId,
  savePendingInterview,
  savePendingInterviewId,
} from "./pendingInterview";

const resumeDraft: InterviewDraft = {
  resume_id: "6f90c619-1ea7-4e2d-9905-7085fb419fd4",
  field_type: "computer_science",
  job_description: null,
  topics: ["programming"],
  language: null,
  level: null,
  duration_minutes: 15,
  video_enabled: false,
};

describe("pending interview storage", () => {
  beforeEach(() => sessionStorage.clear());

  it("round-trips an interview draft", () => {
    savePendingInterview(resumeDraft);

    expect(loadPendingInterview()).toEqual(resumeDraft);
    expect(loadPendingInterviewId()).toBeNull();
  });

  it("keeps the created interview id across a preflight reload", () => {
    savePendingInterview(resumeDraft);
    savePendingInterviewId("interview-123");

    expect(loadPendingInterview()).toEqual(resumeDraft);
    expect(loadPendingInterviewId()).toBe("interview-123");
  });

  it("replaces an old created id when settings are saved again", () => {
    savePendingInterview(resumeDraft);
    savePendingInterviewId("interview-123");
    savePendingInterview({...resumeDraft, duration_minutes: 30});

    expect(loadPendingInterviewId()).toBeNull();
  });

  it("rejects malformed or unsupported drafts", () => {
    sessionStorage.setItem("pending-interview-draft", JSON.stringify({
      ...resumeDraft,
      topics: ["not-a-topic"],
    }));

    expect(loadPendingInterview()).toBeNull();
  });

  it("rejects an area from a different field", () => {
    sessionStorage.setItem("pending-interview-draft", JSON.stringify({
      ...resumeDraft,
      field_type: "physics",
      topics: ["database"],
    }));

    expect(loadPendingInterview()).toBeNull();
  });

  it("clears both the draft and created id", () => {
    savePendingInterview(resumeDraft);
    savePendingInterviewId("interview-123");
    clearPendingInterview();

    expect(loadPendingInterview()).toBeNull();
    expect(loadPendingInterviewId()).toBeNull();
  });
});
