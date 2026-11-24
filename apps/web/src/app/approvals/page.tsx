"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/shell";
import { api, getActiveCompany } from "@/lib/api";

type Suggested = { id: string; label: string; decision: "approved" | "rejected" };
type Approval = {
  id: string;
  action_tag: string;
  title: string;
  status: string;
  payload: Record<string, unknown>;
  waiting_on?: string;
  suggested_actions?: Suggested[];
  decision_note: string | null;
};

const SECTIONS: { key: string; title: string; blurb: string }[] = [
  {
    key: "founder",
    title: "Needs your decision",
    blurb: "The company is waiting on you as Founder.",
  },
  {
    key: "ci",
    title: "Waiting on checks",
    blurb: "Work is paused until automated checks finish.",
  },
  {
    key: "external",
    title: "Waiting outside the company",
    blurb: "Blocked on something external — vendor, partner, or tool.",
  },
];

function humanPayload(payload: Record<string, unknown>): string {
  const skip = new Set(["adapter", "dispatch_id", "raw", "stub"]);
  const bits = Object.entries(payload)
    .filter(([k]) => !skip.has(k))
    .slice(0, 4)
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`);
  return bits.join(" · ") || "Details on file";
}

export default function ApprovalsPage() {
  const [rows, setRows] = useState<Approval[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setRows(await api.requestApprovals(companyId));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  const grouped = useMemo(() => {
    const pending = rows.filter((r) => r.status === "pending");
    const by: Record<string, Approval[]> = { founder: [], ci: [], external: [], other: [] };
    for (const a of pending) {
      const key = a.waiting_on && by[a.waiting_on] ? a.waiting_on : "other";
      by[key].push(a);
    }
    return by;
  }, [rows]);

  const inboxCount = useMemo(
    () => rows.filter((r) => r.status === "pending" && (r.waiting_on || "founder") === "founder").length,
    [rows]
  );

  async function decide(id: string, decision: "approved" | "rejected", note?: string) {
    const companyId = getActiveCompany();
    if (!companyId) return;
    await api.decideApproval(companyId, id, { decision, note: note || `Founder ${decision}` });
    await load();
  }

  function renderCard(a: Approval) {
    const actions = a.suggested_actions?.length
      ? a.suggested_actions
      : [
          { id: "approve", label: "Approve", decision: "approved" as const },
          { id: "reject", label: "Reject", decision: "rejected" as const },
        ];
    return (
      <div key={a.id} className="rounded-xl border border-white/10 bg-ink-900/50 p-4">
        <div className="font-medium">{a.title}</div>
        <p className="text-xs text-mist-500 mt-1">{humanPayload(a.payload)}</p>
        {a.status === "pending" ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {actions.map((s) => (
              <button
                key={s.id}
                onClick={() => decide(a.id, s.decision, s.label)}
                className={
                  s.decision === "approved"
                    ? "text-xs rounded-lg bg-accent text-ink-950 px-3 py-1.5 font-medium"
                    : "text-xs rounded-lg border border-danger/40 text-danger px-3 py-1.5"
                }
              >
                {s.label}
              </button>
            ))}
          </div>
        ) : (
          <span className="text-xs text-mist-400 mt-2 inline-block">{a.decision_note}</span>
        )}
      </div>
    );
  }

  return (
    <Shell title="Needs you" subtitle="Company inbox — decisions only you can make">
      <div className="space-y-6 max-w-3xl">
        <div className="surface rounded-2xl p-6 shadow-panel">
          <p className="text-sm text-mist-300">
            {inboxCount
              ? `${inboxCount} item${inboxCount === 1 ? "" : "s"} waiting on you as Founder.`
              : "Inbox clear — the company isn’t waiting on a Founder decision right now."}
          </p>
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {SECTIONS.map((section) => (
          <section key={section.key} className="surface rounded-2xl p-5 shadow-panel space-y-3">
            <div>
              <h2 className="font-display text-lg">{section.title}</h2>
              <p className="text-xs text-mist-500 mt-1">{section.blurb}</p>
            </div>
            {!grouped[section.key]?.length ? (
              <p className="text-sm text-mist-500">None</p>
            ) : (
              grouped[section.key].map(renderCard)
            )}
          </section>
        ))}

        <section className="surface rounded-2xl p-5 shadow-panel space-y-3">
          <h2 className="font-display text-lg">Recently decided</h2>
          {rows
            .filter((r) => r.status !== "pending")
            .slice(0, 10)
            .map(renderCard)}
          {!rows.some((r) => r.status !== "pending") ? (
            <p className="text-sm text-mist-500">No decisions yet.</p>
          ) : null}
        </section>
      </div>
    </Shell>
  );
}
