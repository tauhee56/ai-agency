import { cn } from "@/lib/cn";

export function StatusChip({
  label,
  ok,
  detail,
}: {
  label: string;
  ok: boolean;
  detail?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3 min-w-[140px]",
        ok ? "border-accent/25 bg-accent/5" : "border-warn/30 bg-warn/5"
      )}
    >
      <div className="text-[11px] uppercase tracking-[0.16em] text-mist-500">{label}</div>
      <div className={cn("mt-1 text-sm font-medium", ok ? "text-accent" : "text-warn")}>
        {ok ? "Online" : "Attention"}
      </div>
      {detail ? <div className="mt-1 text-xs text-mist-400 truncate max-w-[180px]">{detail}</div> : null}
    </div>
  );
}
