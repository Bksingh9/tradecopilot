/** Tiny fetch wrapper. Auth header injected from localStorage. */

/**
 * Resolve the API base URL.
 *
 * Order of precedence:
 *   1. `VITE_API_BASE` env var (set at build time) — preferred for self-hosting.
 *   2. Hostname heuristic — when served from `tradecopilot-web.onrender.com`
 *      the API lives at `tradecopilot-api.onrender.com`.
 *   3. Empty string — same-origin (Vite dev proxy / Caddy reverse-proxy).
 *
 * The hostname heuristic exists because Render's static-site rebuild does not
 * always re-bake env vars cleanly on free tier; this keeps the deployed SPA
 * pointing at the right backend even if the build's env didn't propagate.
 */
function resolveApiBase(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE as string | undefined)?.trim();
  if (fromEnv) return fromEnv.replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    const h = window.location.hostname;
    if (h === "tradecopilot-web.onrender.com") return "https://tradecopilot-api.onrender.com";
  }
  return "";
}

const API_BASE = resolveApiBase();
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
    if (res.status === 401) {
      setToken(null);
      // Don't redirect mid-render; let ProtectedRoute handle it on next render.
    }
    throw new ApiError(extractErrorMessage(payload, res.statusText), res.status, extractErrorCode(payload));
  }
  return payload as T;
}

/**
 * Extracts a human-readable error from any of the shapes our backend may
 * return: TradeCopilotError ({ error: { code, message } }), pydantic 422
 * ({ detail: [{ loc, msg }] }), FastAPI default ({ detail: "..." }), or a
 * plain string body. Falls back to HTTP status text.
 */
function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload) return fallback || "Request failed";
  if (typeof payload === "string") return payload;
  const obj = payload as Record<string, unknown>;
  // Our app: { error: { code, message } }
  const ourErr = obj.error as { message?: string } | undefined;
  if (ourErr && typeof ourErr.message === "string") return ourErr.message;
  // FastAPI default: { detail: string | array }
  const detail = obj.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: unknown) => {
        const item = d as { loc?: unknown[]; msg?: string };
        const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== "body").join(".") : "";
        return loc ? `${loc}: ${item.msg ?? "invalid"}` : (item.msg ?? "invalid");
      })
      .join("; ");
  }
  return fallback || "Request failed";
}

function extractErrorCode(payload: unknown): string | undefined {
  const obj = payload as { error?: { code?: string } } | null;
  return obj?.error?.code;
}

export const api = {
  get: <T,>(p: string, q?: RequestOpts["query"]) => request<T>(p, { method: "GET", query: q }),
  post: <T,>(p: string, body?: unknown, q?: RequestOpts["query"]) =>
    request<T>(p, { method: "POST", body, query: q }),
  put: <T,>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body }),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
};
