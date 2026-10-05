import {StrictMode} from "react";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import type {InterviewDraft, MockInterview} from "../../lib/types";
import {PreflightPage} from "./PreflightPage";
import {apiRequest} from "../../lib/api";

vi.mock("../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../lib/api")>();
  return {...original, apiRequest: vi.fn(), API_URL: "/api"};
});

vi.mock("../../lib/auth", () => ({
  useAuth: () => ({
    user: {id: "user-1", email: "candidate@example.com", full_name: "Practice User"},
    loading: false,
    refetch: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("./audio", () => ({
  startMicCapture: () => ({sampleRate: 16_000, stop: vi.fn()}),
}));

const draft: InterviewDraft = {
  resume_id: "resume-1",
  field_type: "computer_science",
  job_description: null,
  topics: ["programming"],
  language: null,
  level: null,
  duration_minutes: 15,
  video_enabled: false,
};

const preparing: MockInterview = {
  id: "interview-1",
  resume_id: "resume-1",
  field_type: "computer_science",
  topics: ["programming"],
  language: null,
  level: null,
  spoken_language: "en",
  duration_minutes: 15,
  video_enabled: false,
  state: "preparing",
  elapsed_s: 0,
  remaining_s: 900,
  failure_reason: null,
  created_at: "2026-10-02T19:27:39Z",
};

const ready: MockInterview = {...preparing, state: "ready"};

describe("PreflightPage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, {status: 200})));
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{stop: vi.fn()}],
        }),
      },
    });

    vi.mocked(apiRequest).mockImplementation(async (path, options = {}) => {
      if (path === "/mock-interviews" && options.method === "POST") return preparing;
      if (path === "/mock-interviews/interview-1") return ready;
      if (path === "/mock-interviews/interview-1/consent" && options.method === "POST") {
        return ready;
      }
      throw new Error(`Unexpected request: ${options.method ?? "GET"} ${path}`);
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("continues from preparation to the interview room under Strict Mode", async () => {
    render(
      <StrictMode>
        <MemoryRouter initialEntries={[{pathname: "/practice/preflight", state: {draft}}]}>
          <Routes>
            <Route path="/practice/preflight" element={<PreflightPage />} />
            <Route path="/mock-interviews/:interviewId/room" element={<p>Interview room</p>} />
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    fireEvent.click(screen.getByRole("button", {name: "Allow microphone"}));
    await screen.findByRole("button", {name: "Device access confirmed"});
    fireEvent.click(screen.getByRole("checkbox", {name: /Private practice consent/}));
    fireEvent.click(screen.getByRole("button", {name: /Begin interview/}));

    await screen.findByText("Interview room");
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith(
      "/mock-interviews/interview-1/consent",
      {method: "POST"},
    ));
  });
});
