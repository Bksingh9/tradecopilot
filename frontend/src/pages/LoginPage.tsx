import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useLogin } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { Input } from "@/components/Input";

export function LoginPage() {
  const { setAuth } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await login.mutateAsync({ email, password });
      setAuth(res.access_token);
      const dest = (loc.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
      nav(dest, { replace: true });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="min-h-full grid place-items-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="text-2xl font-semibold">TradeCopilot</div>
          <div className="text-xs text-muted mt-1">Risk-managed, process-focused, data-driven.</div>
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
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="text-bad text-xs">{error}</div>}
          <Button variant="primary" type="submit" loading={login.isPending} className="w-full">
            Sign in
          </Button>
          <div className="text-xs text-muted text-center pt-1">
            New here? <Link to="/signup" className="text-accent hover:underline">Create an account</Link>
          </div>
        </form>
        <Disclaimer />
      </div>
    </div>
  );
}
