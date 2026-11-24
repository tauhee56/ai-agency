"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api, setActiveCompany, setToken } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.signup({
        email,
        password,
        name,
        company_name: companyName,
      });
      setToken(res.access_token);
      const memberships = await api.myCompanies();
      if (memberships[0]) setActiveCompany(memberships[0].company_id);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 bg-aurora grid place-items-center px-6 py-12">
      <motion.form
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={onSubmit}
        className="w-full max-w-lg surface rounded-2xl p-8 shadow-panel space-y-4"
      >
        <div>
          <h1 className="font-display text-3xl">Open your company</h1>
          <p className="text-sm text-mist-400 mt-2">
            Day one: we staff departments, seat an AI CEO, and land you on the company Overview.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Your name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Company name</span>
            <input
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
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
          {loading ? "Opening day…" : "Create company"}
        </button>
        <p className="text-sm text-mist-400 text-center">
          Already a Founder?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </motion.form>
    </div>
  );
}
