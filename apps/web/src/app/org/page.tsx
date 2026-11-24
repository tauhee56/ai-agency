"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Pause, Play, Plus } from "lucide-react";
import { Shell } from "@/components/shell";
import {
  api,
  getActiveCompany,
  type Department,
  type Employee,
  type FloorPerson,
  type OrgChartNode,
  type OrgSnapshot,
} from "@/lib/api";
import { workStateLabel } from "@/lib/company-copy";
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
  return (
    <div className={cn(depth > 0 && "ml-6 border-l border-white/10 pl-4")}>
      <div className="relative mb-3 rounded-xl border border-white/10 bg-ink-900/70 px-4 py-3">
        {depth > 0 ? (
          <span className="absolute -left-4 top-5 h-px w-4 bg-white/15" />
        ) : null}
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-medium">{e.title}</div>
            <div className="text-xs text-mist-400 mt-0.5">{deptName(e.department_id)}</div>
          </div>
          <span
            className={cn(
              "text-[10px] uppercase tracking-wider",
              e.status === "active" ? "text-accent" : "text-mist-500"
            )}
          >
            {e.status === "active" ? "On floor" : e.status}
          </span>
        </div>
      </div>
      {node.reports.map((child) => (
        <ChartNode key={child.employee.id} node={child} depth={depth + 1} deptName={deptName} />
      ))}
    </div>
  );
}

function FloorCard({
  person,
  deptName,
  onToggle,
}: {
  person: FloorPerson;
  deptName: (id: string | null) => string;
  onToggle: (emp: Employee) => void;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-white/10 bg-ink-900/55 px-4 py-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium">{person.title}</div>
          <div className="text-xs text-mist-500 mt-0.5">{deptName(person.department_id)}</div>
        </div>
        <span
          className={cn(
            "text-[10px] uppercase tracking-wider",
            person.work_state === "working"
              ? "text-accent"
              : person.work_state === "blocked"
                ? "text-warn"
                : person.work_state === "paused"
                  ? "text-mist-500"
                  : "text-mist-400"
          )}
        >
          {workStateLabel(person.work_state)}
        </span>
      </div>
      <p className="text-sm text-mist-300 mt-3 min-h-[2.5rem]">
        {person.current_task?.title || "Available — waiting for the CEO to assign work"}
      </p>
      <button
        onClick={() => onToggle(person)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs rounded-lg border border-white/10 px-2.5 py-1.5 hover:bg-white/5"
      >
        {person.status === "active" ? (
          <>
            <Pause className="h-3 w-3" /> Pause
          </>
        ) : (
          <>
            <Play className="h-3 w-3" /> Back on floor
          </>
        )}
      </button>
    </motion.div>
  );
}

export default function OrgPage() {
  const [org, setOrg] = useState<OrgSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [deptName, setDeptName] = useState("");
  const [empForm, setEmpForm] = useState({
    title: "",
    codename: "",
    department_id: "",
    manager_employee_id: "",
    role_prompt: "",
    tags: "engineering",
  });

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setOrg(await api.getOrg(companyId));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
    const id = setInterval(() => {
      load().catch(() => undefined);
    }, 8000);
    return () => clearInterval(id);
  }, [load]);

  const deptLabel = useMemo(() => {
    const map = new Map((org?.departments || []).map((d) => [d.id, d.name]));
    return (id: string | null) => (id ? map.get(id) || "—" : "Company-wide");
  }, [org]);

  const floor = useMemo(() => {
    if (org?.floor?.length) return org.floor;
    return (org?.employees || []).map((e) => ({
      ...e,
      work_state: e.status === "paused" ? "paused" : "idle",
      current_task: null,
    }));
  }, [org]);

  const counts = useMemo(() => {
    const working = floor.filter((p) => p.work_state === "working").length;
    const waiting = floor.filter((p) => p.work_state === "blocked").length;
    const available = floor.filter((p) => p.work_state === "idle").length;
    return { working, waiting, available };
  }, [floor]);

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
        role_prompt: empForm.role_prompt || `${empForm.title}`,
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

  return (
    <Shell title="People" subtitle="Who’s on the floor — working, waiting, or available">
      <div className="space-y-6">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="surface rounded-2xl p-6 shadow-panel"
        >
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl">Company floor</h2>
              <p className="text-sm text-mist-400 mt-1">
                Staffed on opening day. Status updates as the CEO assigns work.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-sm">
              <span className="text-accent">{counts.working} working</span>
              <span className="text-warn">{counts.waiting} waiting</span>
              <span className="text-mist-400">{counts.available} available</span>
            </div>
          </div>
        </motion.section>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {floor.map((p) => (
            <FloorCard key={p.id} person={p} deptName={deptLabel} onToggle={toggleStatus} />
          ))}
          {!floor.length ? (
            <p className="text-sm text-mist-400">No people yet — create a company to auto-staff.</p>
          ) : null}
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div className="surface rounded-2xl p-5 shadow-panel">
            <h3 className="font-display text-lg mb-4">Reporting line</h3>
            {org?.chart?.length ? (
              org.chart.map((n) => (
                <ChartNode key={n.employee.id} node={n} deptName={deptLabel} />
              ))
            ) : (
              <p className="text-sm text-mist-400">Org chart appears after opening day.</p>
            )}
          </div>

          <div className="surface rounded-2xl p-5 shadow-panel">
            <h3 className="font-display text-lg mb-2">Departments</h3>
            <ul className="space-y-2">
              {(org?.departments || []).map((d: Department) => (
                <li key={d.id} className="rounded-lg border border-white/10 px-3 py-2 text-sm">
                  <div className="font-medium">{d.name}</div>
                  <div className="text-xs text-mist-500">{d.description || "—"}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="surface rounded-2xl p-5 shadow-panel">
          <button
            type="button"
            onClick={() => setShowAdmin((v) => !v)}
            className="text-sm text-mist-400 hover:text-mist-200"
          >
            {showAdmin ? "Hide org admin" : "Org admin (hire / departments)"}
          </button>
          {showAdmin ? (
            <div className="mt-4 grid md:grid-cols-2 gap-4">
              <form onSubmit={addDepartment} className="space-y-3">
                <h4 className="font-display text-base">Add department</h4>
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
              </form>
              <form onSubmit={addEmployee} className="space-y-3">
                <h4 className="font-display text-base">Hire someone</h4>
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
                  placeholder="Short id (e.g. designer)"
                  className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
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
                <button
                  type="submit"
                  disabled={busy}
                  className="inline-flex items-center gap-2 rounded-lg bg-accent/90 text-ink-950 px-3 py-2 text-sm font-medium disabled:opacity-50"
                >
                  <Plus className="h-4 w-4" /> Hire
                </button>
              </form>
            </div>
          ) : null}
        </div>
      </div>
    </Shell>
  );
}
