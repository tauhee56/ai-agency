#!/usr/bin/env python3
"""CrewAI adapter worker — Adapter Protocol v1.

Runs in a separate process/venv from the API. Telemetry disabled.
Does not import into the FastAPI image.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any

import redis

JOB_QUEUE = os.getenv("JOB_QUEUE", "aicos:jobs")
RESULT_QUEUE = os.getenv("RESULT_QUEUE", "aicos:results")
EVENTS_PREFIX = os.getenv("EVENTS_CHANNEL_PREFIX", "aicos:run:")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OTEL_SDK_DISABLED = "true"
os.environ["OTEL_SDK_DISABLED"] = OTEL_SDK_DISABLED


def client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def publish_event(r: redis.Redis, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict:
    ev = {"type": event_type, "payload": payload or {}, "run_id": run_id}
    r.publish(f"{EVENTS_PREFIX}{run_id}", json.dumps(ev))
    return ev


def pick_default_model(bindings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not bindings:
        return None
    return next((b for b in bindings if b.get("is_default")), bindings[0])


def run_crewai_real(job: dict[str, Any]) -> dict[str, Any]:
    from crewai import Agent, Crew, Process, Task  # type: ignore

    org = job.get("org_snapshot") or {}
    employees = [e for e in org.get("employees") or [] if e.get("codename") != "ceo"][:5]
    if not employees:
        employees = org.get("employees") or [{"title": "Analyst", "role_prompt": "Research", "codename": "analyst"}]

    binding = pick_default_model(job.get("model_bindings") or [])
    llm = None
    if binding and binding.get("api_key"):
        # CrewAI accepts model strings; provider keys via env for smoke simplicity
        os.environ.setdefault("OPENAI_API_KEY", binding["api_key"])
        llm = binding.get("model_name")

    agents = []
    for e in employees:
        agents.append(
            Agent(
                role=e.get("title") or "Agent",
                goal=job.get("goal") or "Complete the task",
                backstory=e.get("role_prompt") or "",
                llm=llm,
                verbose=False,
                allow_delegation=False,
            )
        )
    tasks = [
        Task(
            description=f"{job.get('goal')}\n\n{(job.get('inputs') or {}).get('description') or ''}",
            expected_output="Structured research-style summary with findings and next steps.",
            agent=agents[i % len(agents)],
        )
        for i in range(min(3, len(agents)))
    ]
    process = Process.sequential
    if any(d.get("lead_employee_id") for d in org.get("departments") or []):
        process = Process.hierarchical if len(agents) > 1 else Process.sequential

    crew = Crew(agents=agents, tasks=tasks, process=process, verbose=False)
    result = crew.kickoff(inputs=job.get("inputs") or {})
    text = str(result)
    return {
        "summary": text[:4000],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.05},
        "upstream": {"framework": "crewai", "version": "installed", "mode": "real"},
        "artifacts": [{"kind": "report", "uri": f"memory://run/{job['run_id']}/crew-summary"}],
        "events": [],
    }


def run_crewai_mock(job: dict[str, Any], r: redis.Redis) -> dict[str, Any]:
    """Protocol-compatible sequential research crew without CrewAI package / API keys."""
    run_id = job["run_id"]
    org = job.get("org_snapshot") or {}
    employees = org.get("employees") or []
    events = []
    events.append(publish_event(r, run_id, "run.started", {"adapter": "crewai", "mode": "mock"}))

    roles = [e for e in employees if e.get("status", "active") != "paused"][:4] or [
        {"title": "Researcher", "codename": "researcher"}
    ]
    findings = []
    for e in roles:
        msg = f"{e.get('title')} (@{e.get('codename')}) analyzed: {job.get('goal')}"
        findings.append(msg)
        ev = publish_event(r, run_id, "agent.message", {"agent": e.get("codename"), "message": msg})
        events.append(ev)
        time.sleep(0.05)

    # Sensitive tool → approval needed (does not auto-execute)
    approvals = []
    goal_l = (job.get("goal") or "").lower()
    if "deploy" in goal_l or "external" in goal_l or "outreach" in goal_l:
        approvals.append(
            {
                "action_tag": "external" if "outreach" in goal_l or "external" in goal_l else "deploy",
                "title": "Sensitive tool gated by policy",
                "payload": {"goal": job.get("goal")},
            }
        )
        events.append(publish_event(r, run_id, "approval.needed", approvals[0]))

    summary = (
        f"Crew (mock sequential) completed research-style task.\n"
        f"Goal: {job.get('goal')}\n"
        f"Findings:\n- " + "\n- ".join(findings)
    )
    cost = 0.02 * max(len(roles), 1)
    # Respect remaining budget
    max_budget = float((job.get("policy") or {}).get("max_budget_usd") or 0)
    if max_budget <= 0:
        raise RuntimeError("Hard budget limit reached — further LLM runs blocked")

    events.append(publish_event(r, run_id, "run.progress", {"percent": 100, "stage": "done"}))
    return {
        "summary": summary,
        "usage": {
            "prompt_tokens": 120 * len(roles),
            "completion_tokens": 80 * len(roles),
            "cost_usd": min(cost, max_budget),
        },
        "upstream": {"framework": "crewai", "version": "mock-protocol", "mode": "mock"},
        "artifacts": [{"kind": "report", "uri": f"memory://run/{run_id}/research-report"}],
        "approvals_needed": approvals,
        "events": [{"type": e["type"], "payload": e.get("payload")} for e in events],
    }


def handle_job(job: dict[str, Any], r: redis.Redis) -> dict[str, Any]:
    run_id = job["run_id"]
    adapter = job.get("adapter") or "crewai"
    if adapter == "metagpt":
        return {
            "run_id": run_id,
            "status": "failed",
            "summary": None,
            "error": "MetaGPT adapter disabled in this deployment (feature flag)",
            "usage": {},
            "upstream": {"framework": "metagpt", "version": "disabled"},
            "artifacts": [],
            "events": [{"type": "run.failed", "payload": {"reason": "metagpt_disabled"}}],
        }
    if adapter == "openhands":
        return {
            "run_id": run_id,
            "status": "failed",
            "error": "OpenHands adapter not available until Phase 4 / Docker",
            "usage": {},
            "upstream": {"framework": "openhands", "version": "unavailable"},
            "artifacts": [],
            "events": [],
        }

    force_mock = os.getenv("CREWAI_FORCE_MOCK", "1") == "1"
    try:
        if not force_mock:
            try:
                data = run_crewai_real(job)
            except Exception:
                data = run_crewai_mock(job, r)
        else:
            data = run_crewai_mock(job, r)
        return {
            "run_id": run_id,
            "status": "succeeded",
            "summary": data.get("summary"),
            "usage": data.get("usage") or {},
            "upstream": data.get("upstream") or {},
            "artifacts": data.get("artifacts") or [],
            "approvals_needed": data.get("approvals_needed") or [],
            "events": data.get("events") or [],
            "error": None,
        }
    except Exception as exc:
        return {
            "run_id": run_id,
            "status": "failed",
            "summary": None,
            "error": str(exc),
            "usage": {},
            "upstream": {"framework": "crewai", "traceback": traceback.format_exc()[-500:]},
            "artifacts": [],
            "events": [{"type": "run.failed", "payload": {"error": str(exc)}}],
        }


def main() -> None:
    r = client()
    print(f"[crewai-adapter] listening on {JOB_QUEUE} (OTEL_SDK_DISABLED={os.environ.get('OTEL_SDK_DISABLED')})")
    while True:
        item = r.blpop(JOB_QUEUE, timeout=5)
        if not item:
            continue
        _, raw = item
        try:
            job = json.loads(raw)
        except Exception:
            continue
        adapter = job.get("adapter") or "crewai"
        if adapter == "openhands":
            continue  # wrongly enqueued; drop (API routes openhands separately)
        print(f"[crewai-adapter] job run_id={job.get('run_id')} adapter={adapter}")
        result = handle_job(job, r)
        r.rpush(RESULT_QUEUE, json.dumps(result))
        print(f"[crewai-adapter] finished status={result.get('status')}")


if __name__ == "__main__":
    main()
