"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { ActivityFeed } from "@/components/activity-feed";
import { Shell } from "@/components/shell";
import { api, getActiveCompany } from "@/lib/api";
import { workStateLabel } from "@/lib/company-copy";
import { cn } from "@/lib/cn";

type Overview = Awaited<ReturnType<typeof api.overview>>;

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);

  useEffect(() => {
    const companyId = getActiveCompany();
    if (!companyId) return;
    api.overview(companyId).then(setOverview).catch(() => undefined);
  }, []);

  const pulse = overview?.pulse;

  return (
    <Shell title="Overview" subtitle="Your company’s opening picture">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
        <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-ink-850/70 p-8 shadow-glow">
          <div className="absolute inset-0 bg-aurora opacity-70 pointer-events-none" />
          <div className="absolute inset-0 bg-grid bg-[size:40px_40px] opacity-30 pointer-events-none" />
          <div className="relative">
            <p className="text-[11px] uppercase tracking-[0.22em] text-accent mb-3">Today</p>
            <h2 className="font-display text-4xl md:text-5xl tracking-tight max-w-3xl">
              {overview?.company.name || "Your company"}
            </h2>
            <p className="mt-3 text-mist-300 max-w-2xl">
              Your AI company is staffed. Talk to the CEO in Command Center to open projects — people
              pick up work, and anything that needs a Founder decision lands in Needs you.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <PulseChip label="People" value={pulse?.employees} />
              <PulseChip label="Departments" value={pulse?.departments} />
              <PulseChip label="Active projects" value={pulse?.active_projects} />
              <PulseChip
                label="Needs you"
                value={pulse?.needs_you}
                warn={(pulse?.needs_you || 0) > 0}
              />
              <PulseChip label="At work" value={pulse?.people_working} />
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/command-center"
                className="inline-flex items-center gap-2 rounded-xl bg-accent text-ink-950 px-4 py-2.5 text-sm font-medium"
              >
                Talk to the CEO <ArrowRight className="h-4 w-4" />
              </Link>
              {(pulse?.needs_you || 0) > 0 ? (
                <Link
                  href="/approvals"
                  className="inline-flex items-center gap-2 rounded-xl border border-warn/40 text-warn px-4 py-2.5 text-sm"
                >
                  Review {pulse?.needs_you} waiting
                </Link>
              ) : null}
            </div>
          </div>
        </section>

        <section className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3 space-y-6">
            <div className="surface rounded-2xl p-5 shadow-panel">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-lg">Who’s at work</h3>
                <Link href="/org" className="text-xs text-accent hover:underline">
                  People →
                </Link>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                {(overview?.floor || []).slice(0, 8).map((p) => (
                  <div key={p.id} className="rounded-xl border border-white/10 bg-ink-900/50 px-3 py-3">
                    <div className="flex justify-between gap-2">
                      <div className="font-medium text-sm">{p.title}</div>
                      <span
                        className={cn(
                          "text-[10px] uppercase tracking-wider",
                          p.work_state === "working"
                            ? "text-accent"
                            : p.work_state === "blocked"
                              ? "text-warn"
                              : "text-mist-500"
                        )}
                      >
                        {workStateLabel(p.work_state)}
                      </span>
                    </div>
                    <p className="text-xs text-mist-400 mt-1 line-clamp-2">
                      {p.current_task?.title || "Available for new work"}
                    </p>
                  </div>
                ))}
                {!overview?.floor?.length ? (
                  <p className="text-sm text-mist-400">Staffing your company…</p>
                ) : null}
              </div>
            </div>

            <div className="surface rounded-2xl p-5 shadow-panel">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-lg">Active projects</h3>
              </div>
              <ul className="space-y-2">
                {(overview?.projects || []).map((p) => (
                  <li key={p.id} className="rounded-lg border border-white/10 px-3 py-2">
                    <div className="text-sm font-medium">{p.name}</div>
                    <div className="text-xs text-mist-500 mt-0.5 line-clamp-2">{p.description}</div>
                  </li>
                ))}
                {!overview?.projects?.length ? (
                  <p className="text-sm text-mist-400">No projects yet — ask the CEO to open one.</p>
                ) : null}
              </ul>
            </div>
          </div>

          <div className="lg:col-span-2">
            <ActivityFeed />
          </div>
        </section>
      </motion.div>
    </Shell>
  );
}

function PulseChip({
  label,
  value,
  warn,
}: {
  label: string;
  value?: number;
  warn?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3 min-w-[120px]",
        warn ? "border-warn/30 bg-warn/5" : "border-white/10 bg-ink-900/40"
      )}
    >
      <div className="text-[11px] uppercase tracking-[0.16em] text-mist-500">{label}</div>
      <div className={cn("mt-1 text-xl font-display", warn ? "text-warn" : "text-mist-100")}>
        {value ?? "—"}
      </div>
    </div>
  );
}
