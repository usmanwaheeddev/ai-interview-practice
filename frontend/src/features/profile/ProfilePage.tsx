import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { PageShell } from "../../components/ui/PageShell";
import { apiRequest } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function ProfilePage() {
  const { user, refetch } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");

  const exportData = async () => {
    setBusy(true);
    setError("");
    try {
      const data = await apiRequest<Record<string, unknown>>("/me/data-export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "interview-studio-data-export.json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError("Could not export your data. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const eraseAccount = async () => {
    setBusy(true);
    setError("");
    try {
      await apiRequest<void>("/me/erase", { method: "POST" });
      await refetch();
      navigate("/login", { replace: true });
    } catch {
      setError("Could not erase your account. Please try again.");
      setBusy(false);
    }
  };

  return (
    <PageShell title="Your profile" activeSection="profile">
      <div className="mx-auto grid max-w-3xl gap-6">
        <section>
          <p className="text-sm text-ink-600">Manage your account details and personal data.</p>
        </section>

        {error && <Alert>{error}</Alert>}

        <Card>
          <h2 className="text-lg font-semibold text-ink-900">Account details</h2>
          <dl className="mt-5 grid gap-5 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-ink-500">Name</dt>
              <dd className="mt-1 text-sm text-ink-900">{user?.full_name}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-ink-500">Email</dt>
              <dd className="mt-1 text-sm text-ink-900">{user?.email}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-sm font-medium text-ink-500">Account ID</dt>
              <dd className="mt-1 break-all font-mono text-xs text-ink-700">{user?.id}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold text-ink-900">Export your data</h2>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            Download a JSON copy of your account, resume records, interview history, transcripts, and feedback.
          </p>
          <Button className="mt-5" onClick={() => void exportData()} disabled={busy}>
            {busy ? "Please wait…" : "Download my data"}
          </Button>
        </Card>

        <Card className="border-danger-600/30">
          <h2 className="text-lg font-semibold text-danger-700">Erase your account</h2>
          <p className="mt-2 max-w-2xl text-sm text-ink-600">
            This permanently deletes your account, resumes, interview history, transcripts, reports,
            and stored recordings. Export your data first if you want to keep a copy.
          </p>
          <div className="mt-5 max-w-sm">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-700">Type DELETE to confirm</span>
              <input
                autoComplete="off"
                className="w-full rounded border border-danger-600/40 bg-white px-3 py-2 text-sm text-ink-900 focus:border-danger-600 focus:outline focus:outline-2 focus:outline-danger-200"
                value={deleteConfirmation}
                onChange={(event) => setDeleteConfirmation(event.target.value)}
                disabled={busy}
              />
            </label>
          </div>
          <Button
            variant="danger"
            className="mt-4"
            onClick={() => void eraseAccount()}
            disabled={busy || deleteConfirmation !== "DELETE"}
          >
            Permanently erase my account
          </Button>
        </Card>
      </div>
    </PageShell>
  );
}
