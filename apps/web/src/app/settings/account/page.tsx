"use client";

import { useEffect, useState } from "react";
import { Shell } from "@/components/shell";
import { api, type Membership, type User } from "@/lib/api";

export default function AccountPage() {
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);

  useEffect(() => {
    (async () => {
      setUser(await api.me());
      setMemberships(await api.myCompanies());
    })().catch(() => undefined);
  }, []);

  return (
    <Shell title="Account">
      <div className="surface rounded-2xl p-6 max-w-2xl shadow-panel space-y-6">
        <div>
          <h2 className="font-display text-xl">Founder profile</h2>
          <p className="text-sm text-mist-400 mt-1">Phase 1 account surface.</p>
        </div>
        <dl className="grid sm:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wider text-mist-500">Name</dt>
            <dd className="mt-1">{user?.name || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-mist-500">Email</dt>
            <dd className="mt-1">{user?.email || "—"}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wider text-mist-500">Memberships</dt>
            <dd className="mt-2 space-y-2">
              {memberships.map((m) => (
                <div key={m.id} className="rounded-lg border border-white/10 px-3 py-2">
                  {m.company.name} · <span className="text-mist-400">{m.rbac_role}</span>
                </div>
              ))}
            </dd>
          </div>
        </dl>
      </div>
    </Shell>
  );
}
