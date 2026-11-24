"use client";

import Link from "next/link";
import { Shell } from "@/components/shell";

const LINKS = [
  {
    href: "/settings/models",
    title: "Capabilities",
    blurb: "Which AI providers the company may use. Keys stay encrypted.",
  },
  {
    href: "/playbooks",
    title: "Playbooks & schedules",
    blurb: "Repeatable department playbooks and optional schedules.",
  },
  {
    href: "/settings/account",
    title: "Founder account",
    blurb: "Your profile and memberships.",
  },
];

export default function SettingsPage() {
  return (
    <Shell title="Settings" subtitle="Technical controls — kept out of the day-to-day company floor">
      <div className="max-w-2xl space-y-4">
        <p className="text-sm text-mist-400">
          The company runs from Overview, Command Center, People, and Needs you. Adapter and
          integration details live here so the main product stays company-shaped.
        </p>
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="block surface rounded-2xl p-5 shadow-panel hover:border-accent/30 transition-colors"
          >
            <div className="font-display text-lg">{l.title}</div>
            <p className="text-sm text-mist-400 mt-1">{l.blurb}</p>
          </Link>
        ))}
      </div>
    </Shell>
  );
}
