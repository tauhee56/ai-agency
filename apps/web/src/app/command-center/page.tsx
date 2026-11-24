"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Send } from "lucide-react";
import { ActivityFeed } from "@/components/activity-feed";
import { Shell } from "@/components/shell";
import { api, getActiveCompany } from "@/lib/api";

type DirectResult = Awaited<ReturnType<typeof api.ceoDirect>>;

export default function CommandCenterPage() {
  const [message, setMessage] = useState(
    "Launch project “Launch readiness” — research competitors, draft a product brief, and outline engineering milestones."
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DirectResult | null>(null);
  const [projects, setProjects] = useState<{ id: string; name: string; description: string }[]>([]);
  const [tasks, setTasks] = useState<{ id: string; title: string; status: string }[]>([]);

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    const [p, t] = await Promise.all([api.requestProjects(companyId), api.requestTasks(companyId)]);
    setProjects(p);
    setTasks(t);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.ceoDirect(message, companyId, true);
      setResult(res);
      // give workers a moment then refresh board
      await new Promise((r) => setTimeout(r, 800));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "CEO could not direct the company");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell title="Command Center" subtitle="Talk to your AI CEO — they run the company">
      <div className="grid lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-6">
          <motion.form
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            onSubmit={onSubmit}
            className="surface rounded-2xl p-6 shadow-panel space-y-4"
          >
            <div>
              <h2 className="font-display text-xl">Message the CEO</h2>
              <p className="text-sm text-mist-400 mt-1">
                Describe what you want the company to do. The CEO opens a project, assigns people, and
                starts work — you don’t pick tools or queues.
              </p>
            </div>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={5}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40 resize-y"
              placeholder="e.g. Stand up a research sprint on our market and have Product draft a brief…"
            />
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <button
              type="submit"
              disabled={busy || !message.trim()}
              className="inline-flex items-center gap-2 rounded-xl bg-accent text-ink-950 px-4 py-2.5 text-sm font-medium disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {busy ? "CEO is directing…" : "Send to CEO"}
            </button>
          </motion.form>

          {result ? (
            <div className="surface rounded-2xl p-5 shadow-panel space-y-3">
              <h3 className="font-display text-lg">What the CEO did</h3>
              <p className="text-sm text-mist-200">{result.acknowledgment}</p>
              <div className="text-xs text-mist-500">
                Project · {result.project.name}
                {result.summary.people_assigned?.length
                  ? ` · People · ${result.summary.people_assigned.join(", ")}`
                  : ""}
              </div>
              <ul className="space-y-2">
                {result.tasks.map((t) => (
                  <li key={t.id} className="rounded-lg border border-white/10 px-3 py-2 text-sm">
                    <div className="font-medium">{t.title}</div>
                    <div className="text-xs text-mist-500 mt-0.5">
                      {t.assignee || "Unassigned"}
                      {t.department ? ` · ${t.department}` : ""}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="surface rounded-2xl p-5 shadow-panel">
            <h3 className="font-display text-lg mb-3">Company board</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-mist-500 mb-2">Projects</div>
                <ul className="space-y-2">
                  {projects.slice(0, 6).map((p) => (
                    <li key={p.id} className="text-sm border border-white/10 rounded-lg px-3 py-2">
                      {p.name}
                    </li>
                  ))}
                  {!projects.length ? <li className="text-sm text-mist-500">None yet</li> : null}
                </ul>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-mist-500 mb-2">Work in motion</div>
                <ul className="space-y-2">
                  {tasks
                    .filter((t) => ["ready", "running", "backlog"].includes(t.status))
                    .slice(0, 8)
                    .map((t) => (
                      <li key={t.id} className="text-sm border border-white/10 rounded-lg px-3 py-2">
                        <div>{t.title}</div>
                        <div className="text-[10px] uppercase tracking-wider text-mist-500 mt-0.5">
                          {t.status === "ready" || t.status === "running" ? "In progress" : "Queued"}
                        </div>
                      </li>
                    ))}
                  {!tasks.length ? <li className="text-sm text-mist-500">Ask the CEO to start something</li> : null}
                </ul>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <ActivityFeed title="Live floor" />
        </div>
      </div>
    </Shell>
  );
}
