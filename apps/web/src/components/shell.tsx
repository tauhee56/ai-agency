"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Building2,
  Command,
  LayoutDashboard,
  LogOut,
  Network,
  Settings,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { api, getActiveCompany, setActiveCompany, setToken, type Company, type User } from "@/lib/api";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/command-center", label: "Command Center", icon: Command },
  { href: "/org", label: "Organization", icon: Network },
  { href: "/approvals", label: "Needs you", icon: ShieldCheck },
  { href: "/playbooks", label: "Playbooks", icon: Workflow },
  { href: "/settings/models", label: "Models", icon: Sparkles },
  { href: "/settings/account", label: "Account", icon: Settings },
];

export function Shell({ children, title }: { children: ReactNode; title?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [company, setCompany] = useState<Company | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.me();
        if (cancelled) return;
        setUser(me);
        const memberships = await api.myCompanies();
        if (cancelled) return;
        const preferred = getActiveCompany();
        const chosen =
          memberships.find((m) => m.company_id === preferred)?.company ||
          memberships[0]?.company ||
          null;
        if (chosen) {
          setActiveCompany(chosen.id);
          setCompany(chosen);
        }
        setReady(true);
      } catch {
        setToken(null);
        router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function logout() {
    setToken(null);
    setActiveCompany(null);
    router.replace("/login");
  }

  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center bg-ink-950 bg-aurora">
        <div className="text-mist-400 text-sm tracking-wide">Loading company OS…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ink-950 bg-aurora text-mist-100">
      <div className="flex min-h-screen">
        <aside className="w-64 shrink-0 border-r border-white/10 bg-ink-900/70 backdrop-blur-xl flex flex-col">
          <div className="px-5 py-6 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-accent/15 border border-accent/30 grid place-items-center">
                <Building2 className="h-4 w-4 text-accent" />
              </div>
              <div>
                <div className="font-display text-lg leading-none tracking-tight">AI Company OS</div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-mist-500 mt-1">Phase 1</div>
              </div>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1">
            {NAV.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/");
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                    active
                      ? "bg-accent/10 text-accent border border-accent/20"
                      : "text-mist-200 hover:bg-white/5 border border-transparent"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1">{item.label}</span>
                  {item.stub ? (
                    <span className="text-[10px] uppercase tracking-wider text-mist-500">Soon</span>
                  ) : null}
                </Link>
              );
            })}
          </nav>

          <div className="px-4 py-4 border-t border-white/10 space-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-mist-500">Company</div>
              <div className="text-sm font-medium truncate">{company?.name || "—"}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-mist-500">Founder</div>
              <div className="text-sm truncate">{user?.name}</div>
            </div>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-mist-300 hover:bg-white/5"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </aside>

        <main className="flex-1 min-w-0">
          <header className="sticky top-0 z-20 border-b border-white/10 bg-ink-950/70 backdrop-blur-xl px-8 py-4 flex items-center justify-between">
            <div>
              <motion.h1
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="font-display text-2xl tracking-tight"
              >
                {title || "Overview"}
              </motion.h1>
              <p className="text-sm text-mist-400 mt-0.5">Founder command surface</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-ink-800/60 px-3 py-1 text-xs text-mist-300">
                <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                Live feed ready
              </span>
            </div>
          </header>
          <div className="px-8 py-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
