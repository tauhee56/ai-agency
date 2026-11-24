"use client";

import { Shell } from "@/components/shell";

export function StubPage({ title, blurb }: { title: string; blurb: string }) {
  return (
    <Shell title={title}>
      <div className="surface rounded-2xl p-8 max-w-2xl shadow-panel">
        <p className="text-sm uppercase tracking-[0.2em] text-accent mb-3">Coming soon</p>
        <h2 className="font-display text-3xl tracking-tight mb-3">{title}</h2>
        <p className="text-mist-300 leading-relaxed">{blurb}</p>
      </div>
    </Shell>
  );
}
