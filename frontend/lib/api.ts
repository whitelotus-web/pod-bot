// Simple typed API client for the POD Bot backend.
// All requests go through Next.js rewrites (see next.config.js) so we can use
// relative paths in the browser and the Docker service name on the server.

const TOKEN_KEY = "podbot_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// ---- Typed endpoints ----
export type User = {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
};

export type Campaign = {
  id: number;
  user_id: number;
  name: string;
  niche: string;
  style_prompt: string;
  keyword_sources: string[];
  ai_engine: string;
  ai_model: string | null;
  designs_per_keyword: number;
  product_types: string[];
  base_price_usd: number;
  auto_mode: "semi" | "full";
  target_platforms: string[];
  schedule_cron: string | null;
  last_run_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Keyword = {
  id: number;
  campaign_id: number | null;
  term: string;
  source: string;
  score: number;
  rank: number;
  fetched_at: string;
};

export type Design = {
  id: number;
  campaign_id: number | null;
  keyword_id: number | null;
  title: string;
  prompt: string;
  engine: string;
  model: string | null;
  file_path: string;
  thumbnail_path: string | null;
  status: string;
  created_at: string;
};

export type Product = {
  id: number;
  design_id: number;
  platform_account_id: number;
  external_id: string | null;
  url: string | null;
  title: string;
  description: string;
  tags: string[];
  price_usd: number;
  status: string;
  error: string | null;
  created_at: string;
  published_at: string | null;
};

export type PlatformAccount = {
  id: number;
  user_id: number;
  platform: string;
  label: string;
  shop_id: string | null;
  has_credentials: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AIKey = {
  id: number;
  engine: "gemini" | "openai" | "replicate";
  label: string;
  masked_key: string;
  is_active: boolean;
  created_at: string;
};

export type PromptTemplate = {
  id: string;
  label: string;
  description: string;
  style: string;
  sample_prompt: string;
};

export type AIKeyTestResponse = { ok: boolean; message: string };

export type GenerateResponse = {
  final_prompt: string;
  image_base64: string | null;
  file_path: string | null;
  design_id: number | null;
  engine: string;
  model: string | null;
};

export type RunLog = {
  id: number;
  campaign_id: number | null;
  stage: string;
  status: string;
  message: string | null;
  data: Record<string, unknown> | null;
  started_at: string;
  finished_at: string | null;
};

export function mediaURL(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `/media/${path.replace(/^\/+/, "")}`;
}
