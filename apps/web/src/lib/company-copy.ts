/** Human-facing labels — hide adapter/worker jargon from the company UI. */

const EVENT_LABELS: Record<string, string> = {
  connected: "Pulse online",
  "ceo.directed": "CEO set direction",
  "ceo.advised": "CEO replied",
  "employee.started_work": "Someone started work",
  "project.created": "New project opened",
  "org.seeded": "Company staffed",
  "run.queued": "Work queued",
  "run.finished": "Work finished",
  "run.cancelled": "Work cancelled",
  "approval.decided": "Decision recorded",
  "model.created": "Capability configured",
  "model.updated": "Capability updated",
  "playbook.started": "Playbook started",
  "integration.drafted": "Draft ready for review",
  "department.created": "Department added",
  "employee.created": "Teammate hired",
  "employee.updated": "Teammate updated",
};

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] || type.replace(/\./g, " · ");
}

export function eventBlurb(type: string, payload: Record<string, unknown> = {}): string {
  if (type === "ceo.directed") {
    return `Opened “${payload.project || "a project"}” with ${payload.tasks || "?"} workstreams`;
  }
  if (type === "employee.started_work") {
    return `${payload.who || "Teammate"} → ${payload.task || "a task"}`;
  }
  if (type === "run.finished") {
    return `${payload.status || "done"} on a workstream`;
  }
  if (type === "approval.decided") {
    return String(payload.status || "updated");
  }
  const keys = Object.keys(payload).filter((k) => !["stub", "adapter", "dispatch_id"].includes(k));
  if (!keys.length) return "Company activity";
  const bits = keys.slice(0, 3).map((k) => `${payload[k]}`);
  return bits.join(" · ");
}

export function workStateLabel(state: string): string {
  if (state === "working") return "Working";
  if (state === "blocked") return "Waiting";
  if (state === "paused") return "Paused";
  return "Available";
}
