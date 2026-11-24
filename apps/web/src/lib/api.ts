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
export type Department = {
  id: string;
  company_id: string;
  name: string;
  description: string;
  parent_department_id: string | null;
  lead_employee_id: string | null;
};
export type Employee = {
  id: string;
  company_id: string;
  title: string;
  codename: string;
  role_prompt: string;
  department_id: string | null;
  manager_employee_id: string | null;
  model_config_id: string | null;
  adapter_pref: string | null;
  status: string;
  capabilities: Record<string, unknown>;
};
export type OrgChartNode = { employee: Employee; reports: OrgChartNode[] };
export type OrgSnapshot = {
  departments: Department[];
  employees: Employee[];
  chart: OrgChartNode[];
  ceo: Employee | null;
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
  getOrg: (companyId: string) => request<OrgSnapshot>(`/companies/${companyId}/org`),
  seedOrg: (companyId: string) =>
    request<OrgSnapshot>(`/companies/${companyId}/org/seed`, {
      method: "POST",
      body: JSON.stringify({ template: "startup_default" }),
    }),
  createDepartment: (
    companyId: string,
    body: { name: string; description?: string; parent_department_id?: string | null }
  ) =>
    request<Department>(`/companies/${companyId}/departments`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createEmployee: (companyId: string, body: Record<string, unknown>) =>
    request<Employee>(`/companies/${companyId}/employees`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateEmployee: (companyId: string, employeeId: string, body: Record<string, unknown>) =>
    request<Employee>(`/companies/${companyId}/employees/${employeeId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteEmployee: (companyId: string, employeeId: string) =>
    request<void>(`/companies/${companyId}/employees/${employeeId}`, { method: "DELETE" }),
  requestProjects: (companyId: string) =>
    request<{ id: string; name: string; description: string; status: string }[]>(
      `/companies/${companyId}/projects`
    ),
  createProject: (companyId: string, body: { name: string; description?: string }) =>
    request<{ id: string; name: string; description: string; status: string }>(
      `/companies/${companyId}/projects`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  requestTasks: (companyId: string) =>
    request<{ id: string; title: string; status: string; project_id: string; adapter: string | null }[]>(
      `/companies/${companyId}/tasks`
    ),
  createTask: (companyId: string, body: Record<string, unknown>) =>
    request<{ id: string; title: string; status: string; project_id: string; adapter: string | null }>(
      `/companies/${companyId}/tasks`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  runTask: (companyId: string, taskId: string) =>
    request<{
      id: string;
      task_id: string;
      adapter: string;
      status: string;
      summary: string | null;
      error: string | null;
      usage: Record<string, unknown>;
    }>(`/companies/${companyId}/tasks/${taskId}/run`, { method: "POST" }),
  requestRuns: (companyId: string) =>
    request<
      {
        id: string;
        task_id: string;
        adapter: string;
        status: string;
        summary: string | null;
        error: string | null;
        usage: Record<string, unknown>;
      }[]
    >(`/companies/${companyId}/runs`),
  requestBudget: (companyId: string) =>
    request<{ soft_limit_usd: number; hard_limit_usd: number; spent_usd: number; blocked: boolean }>(
      `/companies/${companyId}/budget`
    ),
  updateBudget: (companyId: string, body: { soft_limit_usd?: number; hard_limit_usd?: number }) =>
    request<{ soft_limit_usd: number; hard_limit_usd: number; spent_usd: number; blocked: boolean }>(
      `/companies/${companyId}/budget`,
      { method: "PATCH", body: JSON.stringify(body) }
    ),
  requestApprovals: (companyId: string) =>
    request<
      {
        id: string;
        action_tag: string;
        title: string;
        status: string;
        payload: Record<string, unknown>;
        waiting_on?: string;
        suggested_actions?: { id: string; label: string; decision: "approved" | "rejected" }[];
        decision_note: string | null;
      }[]
    >(`/companies/${companyId}/approvals`),
  getSoul: (companyId: string, employeeId: string) =>
    request<{ employee_id: string; markdown: string }>(
      `/companies/${companyId}/employees/${employeeId}/soul`
    ),
  putSoul: (companyId: string, employeeId: string, markdown: string) =>
    request<{ employee_id: string; markdown: string }>(
      `/companies/${companyId}/employees/${employeeId}/soul`,
      { method: "PUT", body: JSON.stringify({ markdown }) }
    ),
  listSchedules: (companyId: string) =>
    request<
      {
        id: string;
        playbook_id: string;
        name: string;
        cron: string | null;
        trigger: string;
        enabled: boolean;
        goal_template: string;
        last_run_status: string | null;
      }[]
    >(`/companies/${companyId}/schedules`),
  createSchedule: (companyId: string, body: Record<string, unknown>) =>
    request(`/companies/${companyId}/schedules`, { method: "POST", body: JSON.stringify(body) }),
  updateSchedule: (companyId: string, id: string, body: Record<string, unknown>) =>
    request(`/companies/${companyId}/schedules/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  runSchedule: (companyId: string, id: string) =>
    request(`/companies/${companyId}/schedules/${id}/run`, { method: "POST" }),
  decideApproval: (
    companyId: string,
    approvalId: string,
    body: { decision: "approved" | "rejected"; note?: string }
  ) =>
    request(`/companies/${companyId}/approvals/${approvalId}/decide`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  requestFeatures: () => request<Record<string, unknown>>("/features"),
};
