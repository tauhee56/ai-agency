"use client";

import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/components/shell";
import { api, getActiveCompany } from "@/lib/api";

type Approval = {
  id: string;
  action_tag: string;
  title: string;
  status: string;
  payload: Record<string, unknown>;
  decision_note: string | null;
};

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

  async function decide(id: string, decision: "approved" | "rejected") {
    const companyId = getActiveCompany();
    if (!companyId) return;
    await api.decideApproval(companyId, id, { decision, note: `Founder ${decision}` });
    await load();
  }

  return (
    <Shell title="Approvals">
      <div className="surface rounded-2xl p-6 shadow-panel max-w-3xl space-y-4">
        <p className="text-sm text-mist-400">
          Gates for external / payment / deploy / destructive tools. Phase 3 records approvals from adapter
          policy; Phase 4 adds OpenHands sandbox deploy gates.
        </p>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {!rows.length ? <p className="text-sm text-mist-400">No approvals yet. Run a task mentioning deploy/outreach.</p> : null}
        {rows.map((a) => (
          <div key={a.id} className="rounded-xl border border-white/10 bg-ink-900/50 p-4">
            <div className="flex justify-between gap-3">
              <div>
                <div className="font-medium">{a.title}</div>
                <div className="text-xs text-mist-500 mt-1 font-mono">
                  {a.action_tag} · {a.status}
                </div>
              </div>
              {a.status === "pending" ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => decide(a.id, "approved")}
                    className="text-xs rounded-lg bg-accent text-ink-950 px-3 py-1.5 font-medium"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => decide(a.id, "rejected")}
                    className="text-xs rounded-lg border border-danger/40 text-danger px-3 py-1.5"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <span className="text-xs text-mist-400">{a.decision_note}</span>
              )}
            </div>
            <pre className="mt-2 text-xs text-mist-400 whitespace-pre-wrap">{JSON.stringify(a.payload, null, 2)}</pre>
          </div>
        ))}
      </div>
    </Shell>
  );
}
