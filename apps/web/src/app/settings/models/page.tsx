"use client";

import { FormEvent, useEffect, useState } from "react";
import { Shell } from "@/components/shell";
import { api, getActiveCompany, type ModelConfig } from "@/lib/api";

const PROVIDERS = ["openai", "anthropic", "gemini", "compatible", "local"] as const;

export default function ModelsPage() {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "Default OpenAI",
    provider: "openai",
    model_name: "gpt-4.1",
    base_url: "",
    api_key: "",
    is_default: true,
  });

  async function refresh() {
    const companyId = getActiveCompany();
    if (!companyId) return;
    setModels(await api.listModels(companyId));
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const companyId = getActiveCompany();
    if (!companyId) return;
    setSaving(true);
    setError(null);
    try {
      await api.createModel(companyId, {
        name: form.name,
        provider: form.provider,
        model_name: form.model_name,
        base_url: form.base_url || null,
        api_key: form.api_key || null,
        is_default: form.is_default,
      });
      setForm((f) => ({ ...f, api_key: "" }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function makeDefault(id: string) {
    const companyId = getActiveCompany();
    if (!companyId) return;
    await api.updateModel(companyId, id, { is_default: true });
    await refresh();
  }

  async function remove(id: string) {
    const companyId = getActiveCompany();
    if (!companyId) return;
    await api.deleteModel(companyId, id);
    await refresh();
  }

  return (
    <Shell title="Models">
      <div className="grid lg:grid-cols-2 gap-6">
        <form onSubmit={onSubmit} className="surface rounded-2xl p-6 space-y-4 shadow-panel">
          <div>
            <h2 className="font-display text-xl">Add model provider</h2>
            <p className="text-sm text-mist-400 mt-1">
              Keys are encrypted at rest. Prefer env fallbacks only for local bootstrap.
            </p>
          </div>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Display name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block space-y-1.5">
              <span className="text-xs uppercase tracking-wider text-mist-500">Provider</span>
              <select
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value })}
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1.5">
              <span className="text-xs uppercase tracking-wider text-mist-500">Model</span>
              <input
                required
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
              />
            </label>
          </div>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">Base URL (optional)</span>
            <input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://api.openai.com/v1"
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs uppercase tracking-wider text-mist-500">API key</span>
            <input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-… (stored encrypted)"
              className="w-full rounded-xl bg-ink-900 border border-white/10 px-4 py-3 text-sm outline-none focus:border-accent/40"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-mist-300">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
            />
            Set as company default
          </label>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={saving}
            className="rounded-xl bg-accent text-ink-950 px-4 py-2.5 text-sm font-medium hover:bg-accent-dim disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save model"}
          </button>
        </form>

        <div className="surface rounded-2xl p-6 shadow-panel">
          <h2 className="font-display text-xl mb-4">Configured models</h2>
          <div className="space-y-3">
            {models.length === 0 ? (
              <p className="text-sm text-mist-400">No models yet. CEO stub works offline until you add one.</p>
            ) : (
              models.map((m) => (
                <div key={m.id} className="rounded-xl border border-white/10 bg-ink-900/50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{m.name}</div>
                      <div className="text-xs text-mist-400 mt-1 font-mono">
                        {m.provider}/{m.model_name}
                      </div>
                      <div className="text-xs text-mist-500 mt-1">
                        {m.has_api_key ? "API key on file" : "No key — env fallback may apply"}
                        {m.is_default ? " · default" : ""}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {!m.is_default ? (
                        <button
                          onClick={() => makeDefault(m.id)}
                          className="text-xs rounded-lg border border-white/10 px-2 py-1 hover:bg-white/5"
                        >
                          Default
                        </button>
                      ) : null}
                      <button
                        onClick={() => remove(m.id)}
                        className="text-xs rounded-lg border border-danger/30 text-danger px-2 py-1 hover:bg-danger/10"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
