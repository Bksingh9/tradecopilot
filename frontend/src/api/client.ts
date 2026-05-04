/** Tiny fetch wrapper. Auth header injected from localStorage. */

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
const TOKEN_KEY = "tc_jwt";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

interface RequestOpts {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  /** When true, do not throw on 4xx (used by /health/* polling). */
  swallow?: boolean;
}

function buildUrl(path: string, query?: RequestOpts["query"]): string {
  const url = new URL(API_BASE + path, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  // If API_BASE is absolute, return its full URL; else use just path+query.
  return API_BASE ? url.toString() : url.pathname + url.search;
}

export async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const tok = getToken();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;

  const res = await fetch(buildUrl(path, opts.query), {
    method: opts.method ?? "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
    credentials: "omit",
  });

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    if (opts.swallow) return payload as T;
    const err = (payload as { error?: { code?: string; message?: string } })?.error;
    if (res.status === 401) {
      setToken(null);
      // Don't redirect mid-render; let ProtectedRoute handle it on next render.
    }
    throw new ApiError(
      err?.message ?? res.statusText ?? "Request failed",
      res.status,
      err?.code,
    );
  }
  return payload as T;
}

export const api = {
  get: <T,>(p: string, q?: RequestOpts["query"]) => request<T>(p, { method: "GET", query: q }),
  post: <T,>(p: string, body?: unknown, q?: RequestOpts["query"]) =>
    request<T>(p, { method: "POST", body, query: q }),
  put: <T,>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body }),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
};
