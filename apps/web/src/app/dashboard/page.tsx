"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ActivityFeed } from "@/components/activity-feed";
import { CeoChat } from "@/components/ceo-chat";
import { Shell } from "@/components/shell";
import { StatusChip } from "@/components/status-chip";
import { api, getActiveCompany } from "@/lib/api";

export default function DashboardPage() {
  const [health, setHealth] = useState<{ status: string; db: boolean; redis: boolean } | null>(null);
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof api.overview>> | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
      } catch {
        setHealth({ status: "down", db: false, redis: false });
      }
      const companyId = getActiveCompany();
      if (!companyId) return;
      try {
        setOverview(await api.overview(companyId));
      } catch {
        /* ignore */
      }
    })();
  }, []);

  return (
    <Shell title="Overview">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-8"
      >
        <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-ink-850/70 p-8 shadow-glow">
          <div className="absolute inset-0 bg-aurora opacity-70 pointer-events-none" />
          <div className="absolute inset-0 bg-grid bg-[size:40px_40px] opacity-30 pointer-events-none" />
          <div className="relative">
            <p className="text-[11px] uppercase tracking-[0.22em] text-accent mb-3">Company</p>
            <h2 className="font-display text-4xl md:text-5xl tracking-tight max-w-3xl">
              {overview?.company.name || "Your company"}
            </h2>
            <p className="mt-3 text-mist-300 max-w-2xl">
              Autonomous AI Company OS — Phase 1 foundation. Configure models, brief the AI CEO,
              and watch the live activity feed. Multi-agent adapters arrive in later phases.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <StatusChip label="Database" ok={!!health?.db} />
              <StatusChip label="Redis" ok={!!health?.redis} detail="health / fan-out ready" />
              <StatusChip
                label="Model"
                ok={!!overview?.model_status.configured}
                detail={
                  overview?.model_status.default
                    ? `${overview.model_status.default.provider}/${overview.model_status.default.model}`
                    : "Not configured"
                }
              />
              <StatusChip
                label="AI CEO"
                ok={!!overview?.ceo}
                detail={overview?.ceo?.status || "missing"}
              />
            </div>
          </div>
        </section>

        <section className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <CeoChat />
          </div>
          <div className="lg:col-span-2">
            <ActivityFeed />
          </div>
        </section>
      </motion.div>
    </Shell>
  );
}
