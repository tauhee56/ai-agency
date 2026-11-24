const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function getApiUrl() {
  return API_URL;
}

export function getWsUrl() {
  return WS_URL;
}

export type User = { id: string; email: string; name: string };
export type Company = {
  id: string;
  name: string;
  slug: string;
  status: string;
  founder_user_id: string;
};
export type Membership = {
  id: string;
  company_id: string;
  user_id: string;
  rbac_role: string;
  company: Company;
};
export type ModelConfig = {
  id: string;
  company_id: string;
  name: string;
  provider: string;
  model_name: string;
  base_url: string | null;
  is_default: boolean;
  has_api_key: boolean;
  extra: Record<string, unknown>;
};
export type CeoAdvise = {
  acknowledgment: string;
  plan: Record<string, unknown>;
  raw_markdown: string;
  model_used: string | null;
  stub: boolean;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("aicos_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("aicos_token", t);
  else localStorage.removeItem("aicos_token");
}

export function setActiveCompany(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) localStorage.setItem("aicos_company", id);
  else localStorage.removeItem("aicos_company");
}

export function getActiveCompany(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("aicos_company");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
      if (Array.isArray(detail)) {
        detail = detail.map((d: { msg?: string }) => d.msg || String(d)).join("; ");
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, String(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; db: boolean; redis: boolean }>("/health"),
  signup: (body: {
    email: string;
    password: string;
    name: string;
    company_name: string;
  }) =>
    request<{ access_token: string; user: User }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  login: (body: { email: string; password: string }) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  me: () => request<User>("/auth/me"),
  myCompanies: () => request<Membership[]>("/companies/mine"),
  overview: (companyId: string) =>
    request<{
      company: Company;
      role: string;
      model_status: {
        configured: boolean;
        count: number;
        default: { id: string; name: string; provider: string; model: string } | null;
      };
      ceo: { id: string; title: string; status: string } | null;
      phase: number;
    }>(`/companies/${companyId}/overview`),
  listModels: (companyId: string) => request<ModelConfig[]>(`/companies/${companyId}/models`),
  createModel: (
    companyId: string,
    body: {
      name: string;
      provider: string;
      model_name: string;
      base_url?: string | null;
      api_key?: string | null;
      is_default?: boolean;
      extra?: Record<string, unknown>;
    }
  ) =>
    request<ModelConfig>(`/companies/${companyId}/models`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateModel: (companyId: string, modelId: string, body: Record<string, unknown>) =>
    request<ModelConfig>(`/companies/${companyId}/models/${modelId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteModel: (companyId: string, modelId: string) =>
    request<void>(`/companies/${companyId}/models/${modelId}`, { method: "DELETE" }),
  ceoAdvise: (message: string, companyId?: string) =>
    request<CeoAdvise>("/ceo/advise", {
      method: "POST",
      body: JSON.stringify({ message, company_id: companyId }),
    }),
};
