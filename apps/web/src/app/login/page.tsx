"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.login({ email, password });
      setToken(res.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 bg-aurora flex">
      <div className="hidden lg:flex w-1/2 relative overflow-hidden border-r border-white/10">
        <div
          className="absolute inset-0 opacity-40"
          style={{ backgroundImage: "var(--tw-gradient-stops)" }}
        />
        <div className="absolute inset-0 bg-grid bg-[size:48px_48px] opacity-40" />
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div className="font-display text-2xl tracking-tight">AI Company OS</div>
          <div>
            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="font-display text-5xl leading-[1.05] max-w-md"
            >
              Run your company with agents. You remain Founder.
            </motion.h1>
            <p className="mt-5 text-mist-300 max-w-md leading-relaxed">
              Phase 1 foundation: auth, model registry, dashboard shell, and an AI CEO stub —
              without wiring MetaGPT, CrewAI, or OpenHands yet.
            </p>
          </div>
          <p className="text-xs text-mist-500 uppercase tracking-[0.2em]">Premium dark enterprise</p>
        </div>
      </div>

      <div className="flex-1 grid place-items-center px-6 py-12">
        <motion.form
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={onSubmit}
          className="w-full max-w-md surface rounded-2xl p-8 shadow-panel space-y-5"
        >
          <div>
            <h2 className="font-display text-3xl">Founder login</h2>
            <p className="text-sm text-mist-400 mt-2">Sign in to your company OS.</p>
          </div>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-accent text-ink-950 py-3 text-sm font-medium hover:bg-accent-dim disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-sm text-mist-400 text-center">
            New founder?{" "}
            <Link href="/signup" className="text-accent hover:underline">
              Create company
            </Link>
          </p>
        </motion.form>
      </div>
    </div>
  );
}
