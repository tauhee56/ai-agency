"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/components/shell";
import { api, getActiveCompany, getApiUrl } from "@/lib/api";

type Playbook = {
  id: string;
  name: string;
  department: string;
  description: string;
  adapter: string;
  requires_metagpt?: boolean;
};
type Kpis = {
  runs_total: number;
  runs_by_status: Record<string, number>;
  spend_usd: number;
  artifacts: number;
  memories: number;
  throughput_succeeded: number;
};

async function authed(path: string, init?: RequestInit) {
  const token = localStorage.getItem("aicos_token");
  const res = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [memories, setMemories] = useState<{ id: string; kind: string; content: string }[]>([]);
  const [goal, setGoal] = useState("Summarize TAM and top 3 competitors for AI company OS");
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<string | null>(null);

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    const [pb, kp, mem] = await Promise.all([
      authed(`/companies/${companyId}/playbooks`),
      authed(`/companies/${companyId}/kpis`),
      authed(`/companies/${companyId}/memories`),
    ]);
    setPlaybooks(pb);
    setKpis(kp);
    setMemories(mem.slice(0, 12));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  async function runPlaybook(id: string) {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setError(null);
    try {
      const res = await authed(`/companies/${companyId}/playbooks/run`, {
        method: "POST",
        body: JSON.stringify({ playbook_id: id, goal }),
      });
      setLastRun(res.run_id);
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 400));
        await load();
        const runs = await api.requestRuns(companyId);
        const run = runs.find((x) => x.id === res.run_id);
        if (run && ["succeeded", "failed"].includes(run.status)) break;
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  async function draftSlack() {
    const companyId = getActiveCompany();
    if (!companyId) return;
    await authed(`/companies/${companyId}/integrations/draft`, {
      method: "POST",
      body: JSON.stringify({
        channel: "slack",
        subject: "Weekly ops",
        body: "Draft ops update for #founders — pending approval.",
      }),
    });
    await load();
  }

  return (
    <Shell title="Playbooks">
      <div className="space-y-6">
        <section className="grid sm:grid-cols-4 gap-3">
          {[
            ["Runs", kpis?.runs_total],
            ["Succeeded", kpis?.throughput_succeeded],
            ["Spend USD", kpis?.spend_usd?.toFixed?.(4) ?? kpis?.spend_usd],
            ["Memories", kpis?.memories],
          ].map(([label, value]) => (
            <div key={String(label)} className="surface rounded-xl px-4 py-3 shadow-panel">
              <div className="text-[11px] uppercase tracking-wider text-mist-500">{label}</div>
              <div className="font-display text-2xl mt-1">{value ?? "—"}</div>
            </div>
          ))}
        </section>

        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {lastRun ? <p className="text-xs text-mist-500 font-mono">Last run {lastRun}</p> : null}

        <div className="surface rounded-2xl p-5 shadow-panel space-y-3">
          <h2 className="font-display text-xl">Playbook goal</h2>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            rows={2}
            className="w-full rounded-xl bg-ink-900 border border-white/10 px-3 py-2.5 text-sm outline-none focus:border-accent/40"
          />
          <div className="grid md:grid-cols-2 gap-3">
            {playbooks.map((p) => (
              <div key={p.id} className="rounded-xl border border-white/10 p-4">
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-mist-500 mt-1">
                  {p.department} · {p.adapter}
                  {p.requires_metagpt ? " · MetaGPT required" : ""}
                </div>
                <p className="text-sm text-mist-300 mt-2">{p.description}</p>
                <button
                  disabled={!!p.requires_metagpt}
                  onClick={() => runPlaybook(p.id)}
                  className="mt-3 text-xs rounded-lg bg-accent text-ink-950 px-3 py-1.5 font-medium disabled:opacity-40"
                >
                  Run
                </button>
              </div>
            ))}
          </div>
          <button
            onClick={draftSlack}
            className="text-xs rounded-lg border border-white/10 px-3 py-1.5 hover:bg-white/5"
          >
            Draft Slack message (approval-gated)
          </button>
        </div>

        <div className="surface rounded-2xl p-5 shadow-panel">
          <h2 className="font-display text-xl mb-3">Memory</h2>
          <div className="space-y-2 max-h-72 overflow-auto">
            {memories.map((m) => (
              <div key={m.id} className="rounded-lg border border-white/10 px-3 py-2 text-sm">
                <span className="text-[10px] uppercase tracking-wider text-accent">{m.kind}</span>
                <p className="text-mist-300 mt-1 whitespace-pre-wrap line-clamp-4">{m.content}</p>
              </div>
            ))}
            {!memories.length ? <p className="text-sm text-mist-400">No memories yet.</p> : null}
          </div>
        </div>
      </div>
    </Shell>
  );
}
