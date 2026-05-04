import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getToken, setToken } from "@/api/client";

interface AuthCtx {
  token: string | null;
  setAuth: (token: string | null) => void;
  isAuthed: boolean;
}

const Ctx = createContext<AuthCtx | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken());

  const setAuth = useCallback((t: string | null) => {
    setToken(t);
    setTok(t);
  }, []);

  // Keep state in sync if another tab updates the token.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === "tc_jwt") setTok(e.newValue);
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({ token, setAuth, isAuthed: !!token }),
    [token, setAuth],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
