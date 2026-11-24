"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Pause, Play, Plus, Sprout } from "lucide-react";
import { Shell } from "@/components/shell";
import {
  api,
  getActiveCompany,
  type Department,
  type Employee,
  type OrgChartNode,
  type OrgSnapshot,
} from "@/lib/api";
import { cn } from "@/lib/cn";

function ChartNode({
  node,
  depth = 0,
  deptName,
}: {
  node: OrgChartNode;
  depth?: number;
  deptName: (id: string | null) => string;
}) {
  const e = node.employee;
  const tags = Array.isArray(e.capabilities?.tags) ? (e.capabilities.tags as string[]) : [];
  return (
    <div className={cn(depth > 0 && "ml-6 border-l border-white/10 pl-4")}>
      <div className="relative mb-3 rounded-xl border border-white/10 bg-ink-900/70 px-4 py-3">
        {depth > 0 ? (
          <span className="absolute -left-4 top-5 h-px w-4 bg-white/15" />
        ) : null}
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-medium">{e.title}</div>
            <div className="text-xs text-mist-400 font-mono mt-0.5">@{e.codename}</div>
            <div className="text-xs text-mist-500 mt-1">{deptName(e.department_id)}</div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span
              className={cn(
                "text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 border",
                e.status === "active"
                  ? "border-accent/30 text-accent"
                  : e.status === "paused"
                    ? "border-warn/40 text-warn"
                    : "border-white/15 text-mist-500"
              )}
            >
              {e.status}
            </span>
            {e.adapter_pref ? (
              <span className="text-[10px] text-mist-500 font-mono">{e.adapter_pref}</span>
            ) : null}
          </div>
        </div>
        {tags.length ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {tags.map((t) => (
              <span key={t} className="text-[10px] rounded border border-white/10 px-1.5 py-0.5 text-mist-400">
                {t}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      {node.reports.map((child) => (
        <ChartNode key={child.employee.id} node={child} depth={depth + 1} deptName={deptName} />
      ))}
    </div>
  );
}

export default function OrgPage() {
  const [org, setOrg] = useState<OrgSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [deptName, setDeptName] = useState("");
  const [empForm, setEmpForm] = useState({
    title: "",
    codename: "",
    department_id: "",
    manager_employee_id: "",
    role_prompt: "",
    tags: "engineering",
  });
  const [soulEmpId, setSoulEmpId] = useState("");
  const [soulMd, setSoulMd] = useState("");
  const [soulBusy, setSoulBusy] = useState(false);

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setOrg(await api.getOrg(companyId));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  const deptLabel = useMemo(() => {
    const map = new Map((org?.departments || []).map((d) => [d.id, d.name]));
    return (id: string | null) => (id ? map.get(id) || "—" : "Unassigned");
  }, [org]);

  async function seed() {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setBusy(true);
    setError(null);
    try {
      setOrg(await api.seedOrg(companyId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    } finally {
      setBusy(false);
    }
  }

  async function addDepartment(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId || !deptName.trim()) return;
    setBusy(true);
    try {
      await api.createDepartment(companyId, { name: deptName.trim() });
      setDeptName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function addEmployee(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId) return;
    setBusy(true);
    try {
      const tags = empForm.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await api.createEmployee(companyId, {
        title: empForm.title,
        codename: empForm.codename,
        role_prompt: empForm.role_prompt || `${empForm.title} agent`,
        department_id: empForm.department_id || null,
        manager_employee_id: empForm.manager_employee_id || org?.ceo?.id || null,
        status: "active",
        capabilities: { tags, tools: [] },
      });
      setEmpForm({
        title: "",
        codename: "",
        department_id: "",
        manager_employee_id: org?.ceo?.id || "",
        role_prompt: "",
        tags: "engineering",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus(emp: Employee) {
    const companyId = getActiveCompany();
    if (!companyId) return;
    const next = emp.status === "active" ? "paused" : "active";
    await api.updateEmployee(companyId, emp.id, { status: next });
    await load();
  }

  async function loadSoul(employeeId: string) {
    const companyId = getActiveCompany();
    if (!companyId || !employeeId) return;
    setSoulEmpId(employeeId);
    setSoulBusy(true);
    try {
      const res = await api.getSoul(companyId, employeeId);
      setSoulMd(res.markdown);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Soul load failed");
    } finally {
      setSoulBusy(false);
    }
  }

  async function saveSoul() {
    const companyId = getActiveCompany();
    if (!companyId || !soulEmpId) return;
    setSoulBusy(true);
    try {
      const res = await api.putSoul(companyId, soulEmpId, soulMd);
      setSoulMd(res.markdown);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Soul save failed");
    } finally {
      setSoulBusy(false);
    }
  }

  return (
    <Shell title="Organization">
      <div className="space-y-6">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="surface rounded-2xl p-6 shadow-panel flex flex-wrap items-center justify-between gap-4"
        >
          <div>
            <h2 className="font-display text-2xl">Org chart</h2>
            <p className="text-sm text-mist-400 mt-1">
              AI CEO is the root manager. Seed a startup template or craft the hierarchy by hand.
            </p>
          </div>
          <button
            onClick={seed}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-xl bg-accent text-ink-950 px-4 py-2.5 text-sm font-medium hover:bg-accent-dim disabled:opacity-50"
          >
            <Sprout className="h-4 w-4" />
            Seed startup template
          </button>
        </motion.section>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="grid xl:grid-cols-5 gap-6">
          <div className="xl:col-span-3 space-y-4">
            <div className="surface rounded-2xl p-5 shadow-panel">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-lg">Reporting hierarchy</h3>
                <span className="text-xs text-mist-500">
                  {org?.employees.length || 0} employees · {org?.departments.length || 0} departments
                </span>
              </div>
              {org?.chart?.length ? (
                org.chart.map((n) => (
                  <ChartNode key={n.employee.id} node={n} deptName={deptLabel} />
                ))
              ) : (
                <p className="text-sm text-mist-400">No employees yet.</p>
              )}
            </div>
          </div>

          <div className="xl:col-span-2 space-y-4">
            <form onSubmit={addDepartment} className="surface rounded-2xl p-5 space-y-3 shadow-panel">
              <h3 className="font-display text-lg">Add department</h3>
              <input
                value={deptName}
                onChange={(e) => setDeptName(e.target.value)}
                placeholder="e.g. Design"
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
              />
              <button
                type="submit"
                disabled={busy || !deptName.trim()}
                className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5 disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> Add
              </button>
              <ul className="space-y-2 pt-2">
                {(org?.departments || []).map((d: Department) => (
                  <li key={d.id} className="rounded-lg border border-white/10 px-3 py-2 text-sm">
                    <div className="font-medium">{d.name}</div>
                    <div className="text-xs text-mist-500">{d.description || "—"}</div>
                  </li>
                ))}
              </ul>
            </form>

            <form onSubmit={addEmployee} className="surface rounded-2xl p-5 space-y-3 shadow-panel">
              <h3 className="font-display text-lg">Add employee</h3>
              <input
                required
                value={empForm.title}
                onChange={(e) => setEmpForm({ ...empForm, title: e.target.value })}
                placeholder="Title"
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
              />
              <input
                required
                value={empForm.codename}
                onChange={(e) => setEmpForm({ ...empForm, codename: e.target.value })}
                placeholder="codename"
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm font-mono outline-none focus:border-accent/40"
              />
              <select
                value={empForm.department_id}
                onChange={(e) => setEmpForm({ ...empForm, department_id: e.target.value })}
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
              >
                <option value="">No department</option>
                {(org?.departments || []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
              <select
                value={empForm.manager_employee_id}
                onChange={(e) => setEmpForm({ ...empForm, manager_employee_id: e.target.value })}
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
              >
                <option value="">Manager: AI CEO (default)</option>
                {(org?.employees || []).map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.title} (@{emp.codename})
                  </option>
                ))}
              </select>
              <input
                value={empForm.tags}
                onChange={(e) => setEmpForm({ ...empForm, tags: e.target.value })}
                placeholder="capability tags (comma)"
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
              />
              <button
                type="submit"
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-lg bg-accent/90 text-ink-950 px-3 py-2 text-sm font-medium disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> Hire agent
              </button>
            </form>

            <div className="surface rounded-2xl p-5 shadow-panel">
              <h3 className="font-display text-lg mb-3">Status controls</h3>
              <div className="space-y-2 max-h-64 overflow-auto">
                {(org?.employees || []).map((emp) => (
                  <div key={emp.id} className="flex items-center justify-between gap-2 text-sm border border-white/10 rounded-lg px-3 py-2">
                    <span>
                      {emp.title}{" "}
                      <span className="text-mist-500 font-mono text-xs">@{emp.codename}</span>
                    </span>
                    <div className="flex gap-1">
                      <button
                        onClick={() => loadSoul(emp.id)}
                        className="text-xs rounded border border-white/10 px-2 py-1 hover:bg-white/5"
                      >
                        Soul
                      </button>
                      <button
                        onClick={() => toggleStatus(emp)}
                        className="inline-flex items-center gap-1 text-xs rounded border border-white/10 px-2 py-1 hover:bg-white/5"
                      >
                        {emp.status === "active" ? (
                          <>
                            <Pause className="h-3 w-3" /> Pause
                          </>
                        ) : (
                          <>
                            <Play className="h-3 w-3" /> Activate
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="surface rounded-2xl p-5 shadow-panel space-y-3">
              <h3 className="font-display text-lg">Employee Soul (Markdown)</h3>
              <p className="text-xs text-mist-500">
                Reviewable SOUL + pinned MEMORY — maps to role_prompt + employee-scoped memories.
              </p>
              <textarea
                value={soulMd}
                onChange={(e) => setSoulMd(e.target.value)}
                rows={12}
                placeholder="Select Soul on an employee…"
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-xs font-mono outline-none focus:border-accent/40"
              />
              <button
                disabled={soulBusy || !soulEmpId}
                onClick={saveSoul}
                className="text-xs rounded-lg bg-accent text-ink-950 px-3 py-1.5 font-medium disabled:opacity-40"
              >
                Save Soul
              </button>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
