import { Link } from "react-router-dom";

export function PrivacyNoticePage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-semibold">Mock Interview Privacy Notice</h1>
      <p>AI uses your resume, job description, and selected topics for personal practice.
        Choose 15 or 30 minutes. Questions are spoken and shown as text.</p>
      <p>Your microphone audio and transcript are recorded. Camera recording is optional.
        Recordings are for your review. Feedback uses answer content, not appearance,
        facial expressions, or eye contact.</p>
      <p>Reports include topic ratings, strengths, weaknesses, and practice suggestions.
        AI feedback can be inaccurate and is not an employment decision.
        Failed scoring can be retried after service recovery.</p>
      <p>Configured providers process resume/interview text and speech audio.
        Data is retained until deleted; no automatic expiry is currently configured.
        Personal data export and deletion are available through the authenticated
        /api/me/data-export and /api/me/erase endpoints.</p>
      <Link to="/practice/new" className="text-brand-600 hover:underline">Back to practice</Link>
    </div>
  );
}
