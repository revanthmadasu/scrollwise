// Thin typed fetch client for the ScrollWise API.
//
// Holds the JWT pair in localStorage, attaches the access token, and
// transparently retries once after refreshing on a 401.

import type {
  AnswerResult,
  FeedResponse,
  Interests,
  Progress,
  Prompt,
  ReactionResult,
  Post,
  Reaction,
  TokenPair,
  Topic,
  User,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const ACCESS_KEY = "sw_access";
const REFRESH_KEY = "sw_refresh";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: any) => d.msg).join(", ");
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

async function refreshTokens(): Promise<boolean> {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    tokenStore.clear();
    return false;
  }
  tokenStore.set(await res.json());
  return true;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // attach access token (default true)
  _retry?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, _retry = false } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && tokenStore.access) headers["Authorization"] = `Bearer ${tokenStore.access}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && !_retry) {
    if (await refreshTokens()) {
      return request<T>(path, { ...opts, _retry: true });
    }
  }
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- auth ---
  register: (email: string, password: string, display_name?: string) =>
    request<TokenPair>("/auth/register", {
      method: "POST",
      auth: false,
      body: { email, password, display_name },
    }),
  login: (email: string, password: string) =>
    request<TokenPair>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
  loginWithGoogle: (id_token: string) =>
    request<TokenPair>("/auth/google", { method: "POST", auth: false, body: { id_token } }),
  me: () => request<User>("/auth/me"),

  // --- interests ---
  topics: () => request<Topic[]>("/interests"),
  getInterests: () => request<Interests>("/me/interests"),
  setInterests: (topic_ids: string[]) =>
    request<Interests>("/me/interests", { method: "PUT", body: { topic_ids } }),

  // --- prompts ---
  createPrompt: (prompt_text: string) =>
    request<Prompt>("/me/prompts", { method: "POST", body: { prompt_text } }),
  listPrompts: () => request<Prompt[]>("/me/prompts"),

  // --- feed / posts ---
  feed: (limit = 10) => request<FeedResponse>(`/feed?limit=${limit}`),
  getPost: (id: string) => request<Post>(`/posts/${id}`),
  react: (id: string, reaction: Reaction | null) =>
    request<ReactionResult>(`/posts/${id}/reaction`, { method: "PUT", body: { reaction } }),
  answer: (id: string, selected_index: number) =>
    request<AnswerResult>(`/posts/${id}/answer`, { method: "POST", body: { selected_index } }),
  revise: (id: string) => request<Post[]>(`/posts/${id}/revise`),

  // --- progress ---
  progress: () => request<Progress>("/me/progress"),
};

export { BASE as API_BASE };
