import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useSignup } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { Input } from "@/components/Input";

export function SignupPage() {
  const { setAuth } = useAuth();
  const nav = useNavigate();
  const signup = useSignup();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await signup.mutateAsync({ email, password });
      setAuth(res.access_token);
      nav("/", { replace: true });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="min-h-full grid place-items-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="text-2xl font-semibold">Create account</div>
          <div className="text-xs text-muted mt-1">A personal tenant is created for you.</div>
        </div>
        <form onSubmit={onSubmit} className="card space-y-3">
          <Input
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            hint="At least 8 characters."
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="text-bad text-xs">{error}</div>}
          <Button variant="primary" type="submit" loading={signup.isPending} className="w-full">
            Create account
          </Button>
          <div className="text-xs text-muted text-center pt-1">
            Already have one? <Link to="/login" className="text-accent hover:underline">Sign in</Link>
          </div>
        </form>
        <Disclaimer />
      </div>
    </div>
  );
}
