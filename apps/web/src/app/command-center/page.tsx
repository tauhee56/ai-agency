"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, RefreshCw } from "lucide-react";
import { Shell } from "@/components/shell";
import { api, getActiveCompany, getWsUrl } from "@/lib/api";

type Project = { id: string; name: string; description: string; status: string };
type Task = { id: string; title: string; status: string; project_id: string; adapter: string | null };
type Run = {
  id: string;
  task_id: string;
  adapter: string;
  status: string;
  summary: string | null;
  error: string | null;
  usage: Record<string, unknown>;
};
type Budget = {
  soft_limit_usd: number;
  hard_limit_usd: number;
  spent_usd: number;
  blocked: boolean;
};

export default function CommandCenterPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [features, setFeatures] = useState<Record<string, unknown> | null>(null);
  const [projectName, setProjectName] = useState("Research sprint");
  const [taskTitle, setTaskTitle] = useState("Research competitor landscape for our AI company OS");
  const [selectedProject, setSelectedProject] = useState("");
  const [activeRun, setActiveRun] = useState<string | null>(null);
  const [liveEvents, setLiveEvents] = useState<{ type: string; payload?: unknown }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    const [p, t, r, b, f] = await Promise.all([
      api.requestProjects(companyId),
      api.requestTasks(companyId),
      api.requestRuns(companyId),
      api.requestBudget(companyId),
      api.requestFeatures(),
    ]);
    setProjects(p);
    setTasks(t);
    setRuns(r);
    setBudget(b);
    setFeatures(f);
    if (!selectedProject && p[0]) setSelectedProject(p[0].id);
  }, [selectedProject]);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  useEffect(() => {
    if (!activeRun) return;
    const token = localStorage.getItem("aicos_token");
    if (!token) return;
    const ws = new WebSocket(`${getWsUrl()}/ws/runs/${activeRun}?token=${encodeURIComponent(token)}`);
    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        setLiveEvents((prev) => [...prev, data].slice(-40));
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, [activeRun]);

  async function createProject(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId) return;
    setBusy(true);
    try {
      const p = await api.createProject(companyId, { name: projectName, description: "Phase 3 project" });
      setSelectedProject(p.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function createAndRun(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId || !selectedProject) return;
    setBusy(true);
    setError(null);
    setLiveEvents([]);
    try {
      const task = await api.createTask(companyId, {
        title: taskTitle,
        description: "Produce a research-style summary with findings and next steps.",
        project_id: selectedProject,
        adapter: "crewai",
      });
      const run = await api.runTask(companyId, task.id);
      setActiveRun(run.id);
      // poll until finished
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 400));
        await load();
        const latest = (await api.requestRuns(companyId)).find((x) => x.id === run.id);
        if (latest && ["succeeded", "failed", "cancelled", "timed_out"].includes(latest.status)) break;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell title="Command Center">
      <div className="space-y-6">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="surface rounded-2xl p-5 shadow-panel flex flex-wrap gap-4 justify-between"
        >
          <div>
            <h2 className="font-display text-2xl">Multi-agent runs</h2>
            <p className="text-sm text-mist-400 mt-1">
              CrewAI adapter via Redis job queue. MetaGPT:{" "}
              <span className="text-warn">{String((features as { metagpt_status?: string })?.metagpt_status || "…")}</span>
            </p>
          </div>
          <div className="flex gap-3 text-sm">
            <div className="rounded-xl border border-white/10 px-4 py-2">
              <div className="text-[11px] uppercase tracking-wider text-mist-500">Budget spent</div>
              <div className="font-mono">
                ${Number(budget?.spent_usd || 0).toFixed(4)} / ${Number(budget?.hard_limit_usd || 0).toFixed(2)}
              </div>
            </div>
            <div
              className={`rounded-xl border px-4 py-2 ${budget?.blocked ? "border-danger/40 text-danger" : "border-accent/30 text-accent"}`}
            >
              {budget?.blocked ? "Hard stop ON" : "Runs allowed"}
            </div>
            <button onClick={() => load()} className="rounded-xl border border-white/10 px-3 hover:bg-white/5">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </motion.section>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="grid lg:grid-cols-2 gap-6">
          <form onSubmit={createProject} className="surface rounded-2xl p-5 space-y-3 shadow-panel">
            <h3 className="font-display text-lg">Project</h3>
            <input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-accent text-ink-950 px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              Create project
            </button>
            <ul className="text-sm space-y-1 pt-2">
              {projects.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => setSelectedProject(p.id)} className="text-left hover:text-accent">
                    {p.name} {selectedProject === p.id ? "✓" : ""}
                  </button>
                </li>
              ))}
            </ul>
          </form>

          <form onSubmit={createAndRun} className="surface rounded-2xl p-5 space-y-3 shadow-panel">
            <h3 className="font-display text-lg">Enqueue CrewAI task</h3>
            <textarea
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              rows={3}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
            />
            <button
              type="submit"
              disabled={busy || !selectedProject}
              className="inline-flex items-center gap-2 rounded-lg bg-accent text-ink-950 px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {busy ? "Running…" : "Run with CrewAI"}
            </button>
          </form>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div className="surface rounded-2xl p-5 shadow-panel">
            <h3 className="font-display text-lg mb-3">Recent runs</h3>
            <div className="space-y-2 max-h-80 overflow-auto">
              {runs.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    setActiveRun(r.id);
                    setLiveEvents([]);
                  }}
                  className="w-full text-left rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5"
                >
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-xs text-accent">{r.adapter}</span>
                    <span className="text-xs text-mist-400">{r.status}</span>
                  </div>
                  <div className="mt-1 text-mist-300 line-clamp-2">{r.summary || r.error || r.id}</div>
                </button>
              ))}
              {!runs.length ? <p className="text-sm text-mist-400">No runs yet.</p> : null}
            </div>
            <div className="mt-4 text-xs text-mist-500">Tasks: {tasks.length}</div>
          </div>

          <div className="surface rounded-2xl p-5 shadow-panel">
            <h3 className="font-display text-lg mb-3">Live run stream</h3>
            <div className="space-y-2 max-h-80 overflow-auto font-mono text-xs">
              {liveEvents.map((e, i) => (
                <div key={i} className="border border-white/10 rounded px-2 py-1">
                  <span className="text-accent">{e.type}</span>{" "}
                  <span className="text-mist-400">{JSON.stringify(e.payload || {})}</span>
                </div>
              ))}
              {!liveEvents.length ? <p className="text-sm text-mist-400 font-sans">Select or start a run.</p> : null}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
