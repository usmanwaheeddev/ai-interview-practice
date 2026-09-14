import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest, ApiError } from "../../lib/api";
import { useAuth, type CurrentUser } from "../../lib/auth";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Field";
import { PublicShell } from "../../components/ui/PageShell";

export function LoginPage() {
  const [email, setEmail] = useState("candidate@example.com");
  const [password, setPassword] = useState("devpassword123");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { refetch } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiRequest<CurrentUser>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      await refetch();
      navigate("/practice/new");
    } catch (err) {
      setError(err instanceof ApiError
        ? err.message
        : "Cannot reach the interview server. Start the Backend API configuration in PyCharm and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PublicShell title="Log in">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="Email">
          <Input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={submitting}>
          {submitting ? "Logging in…" : "Log in"}
        </Button>
      </form>
      <p className="text-sm text-ink-500">
        <Link to="/register" className="font-medium text-brand-600 hover:underline">
          Create an account
        </Link>
      </p>
    </PublicShell>
  );
}
