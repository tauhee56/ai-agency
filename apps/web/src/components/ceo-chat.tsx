"use client";

import { FormEvent, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send } from "lucide-react";
import { api, getActiveCompany, type CeoAdvise } from "@/lib/api";

export function CeoChat() {
  const [message, setMessage] = useState("Draft a 30-day plan to stand up our autonomous AI company.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CeoAdvise | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const companyId = getActiveCompany() || undefined;
      const res = await api.ceoAdvise(message, companyId);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="surface rounded-2xl p-5 shadow-panel">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="font-display text-lg">AI CEO</h2>
          <p className="text-sm text-mist-400 mt-1">
            Phase 1 stub — structured acknowledgment and plan. No multi-agent tools.
          </p>
        </div>
        {result ? (
          <span className="text-[11px] uppercase tracking-wider rounded-full border border-white/10 px-2.5 py-1 text-mist-400">
            {result.stub ? "Offline stub" : result.model_used || "Live model"}
          </span>
        ) : null}
      </div>

      <form onSubmit={onSubmit} className="space-y-3">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40 resize-y"
          placeholder="Message the AI CEO…"
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <button
          type="submit"
          disabled={loading || !message.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-accent text-ink-950 px-4 py-2.5 text-sm font-medium hover:bg-accent-dim disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {loading ? "Thinking…" : "Ask CEO"}
        </button>
      </form>

      <AnimatePresence>
        {result ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-5 rounded-xl border border-white/10 bg-ink-900/60 p-4 space-y-3"
          >
            <div>
              <div className="text-[11px] uppercase tracking-wider text-mist-500">Acknowledgment</div>
              <p className="mt-1 text-sm">{result.acknowledgment}</p>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-mist-500">Plan</div>
              <pre className="mt-2 text-xs text-mist-200 whitespace-pre-wrap font-mono leading-relaxed">
                {JSON.stringify(result.plan, null, 2)}
              </pre>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
