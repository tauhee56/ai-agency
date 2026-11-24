"use client";

import { useEffect, useState } from "react";
import { getActiveCompany, getWsUrl } from "@/lib/api";

type Event = { type: string; payload?: Record<string, unknown>; at?: string };

export function ActivityFeed() {
  const [events, setEvents] = useState<Event[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const companyId = getActiveCompany();
    const token = localStorage.getItem("aicos_token");
    if (!companyId || !token) return;

    const ws = new WebSocket(`${getWsUrl()}/ws/activity/${companyId}?token=${encodeURIComponent(token)}`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as Event;
        if (data.type === "ping") return;
        setEvents((prev) => [data, ...prev].slice(0, 30));
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, []);

  return (
    <div className="surface rounded-2xl p-5 shadow-panel h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-lg">Live activity</h2>
        <span className="text-xs text-mist-500">{connected ? "WebSocket connected" : "Connecting…"}</span>
      </div>
      <div className="space-y-3 max-h-[420px] overflow-auto pr-1">
        {events.length === 0 ? (
          <p className="text-sm text-mist-400">
            Waiting for events. Configure a model or ask the AI CEO to generate activity.
          </p>
        ) : (
          events.map((e, i) => (
            <div key={`${e.at}-${i}`} className="rounded-lg border border-white/8 bg-ink-900/50 px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-xs text-accent">{e.type}</span>
                <span className="text-[11px] text-mist-500">{e.at ? new Date(e.at).toLocaleTimeString() : ""}</span>
              </div>
              <pre className="mt-1 text-xs text-mist-300 whitespace-pre-wrap break-words">
                {JSON.stringify(e.payload || {}, null, 0)}
              </pre>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
