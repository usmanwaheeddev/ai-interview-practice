import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Field";
import {PasswordInput} from "../../components/ui/PasswordInput";
import { PublicShell } from "../../components/ui/PageShell";

function isGmailAddress(value: string) {
  return value.trim().toLowerCase().endsWith("@gmail.com");
}

export function RegisterCandidatePage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { refetch } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!isGmailAddress(email)) {
      setError("Please use a Gmail address.");
      return;
    }
    setSubmitting(true);
    try {
      await apiRequest("/auth/register", {
        method: "POST",
        body: { full_name: fullName, email, password },
      });
      await refetch();
      navigate("/practice/new");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PublicShell title="Create your account">
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="Full name">
          <Input required value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        <Field label="Email">
          <Input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Password">
          <PasswordInput
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create account"}
        </Button>
      </form>
    </PublicShell>
  );
}
