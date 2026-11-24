#!/usr/bin/env python3
"""CrewAI adapter worker — Adapter Protocol v1.1.

dispatch_id + heartbeat + single terminal completion.
"""

from __future__ import annotations

import json
import os
import time
import traceback
from datetime import UTC, datetime
from typing import Any

import redis

JOB_QUEUE = os.getenv("JOB_QUEUE", "aicos:jobs")
RESULT_QUEUE = os.getenv("RESULT_QUEUE", "aicos:results")
HEARTBEAT_QUEUE = os.getenv("HEARTBEAT_QUEUE", "aicos:heartbeats")
EVENTS_PREFIX = os.getenv("EVENTS_CHANNEL_PREFIX", "aicos:run:")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
os.environ["OTEL_SDK_DISABLED"] = "true"


def client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def publish_event(r: redis.Redis, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict:
    ev = {"type": event_type, "payload": payload or {}, "run_id": run_id}
    r.publish(f"{EVENTS_PREFIX}{run_id}", json.dumps(ev))
    return ev


def heartbeat(r: redis.Redis, job: dict[str, Any]) -> None:
    r.rpush(
        HEARTBEAT_QUEUE,
        json.dumps(
            {
                "run_id": job["run_id"],
                "dispatch_id": job.get("dispatch_id"),
                "at": datetime.now(UTC).isoformat(),
            }
        ),
    )


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
        os.environ.setdefault("OPENAI_API_KEY", binding["api_key"])
        llm = binding.get("model_name")

    agents = [
        Agent(
            role=e.get("title") or "Agent",
            goal=job.get("goal") or "Complete the task",
            backstory=e.get("role_prompt") or "",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        for e in employees
    ]
    tasks = [
        Task(
            description=f"{job.get('goal')}\n\n{(job.get('inputs') or {}).get('description') or ''}",
            expected_output="Structured research-style summary with findings and next steps.",
            agent=agents[i % len(agents)],
        )
        for i in range(min(3, len(agents)))
    ]
    process = Process.hierarchical if len(agents) > 1 else Process.sequential
    crew = Crew(agents=agents, tasks=tasks, process=process, verbose=False)
    result = crew.kickoff(inputs=job.get("inputs") or {})
    return {
        "summary": str(result)[:4000],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.05},
        "upstream": {"framework": "crewai", "version": "installed", "mode": "real"},
        "artifacts": [{"kind": "report", "uri": f"memory://run/{job['run_id']}/crew-summary"}],
        "events": [],
        "approvals_needed": [],
    }


def run_crewai_mock(job: dict[str, Any], r: redis.Redis) -> dict[str, Any]:
    run_id = job["run_id"]
    dispatch_id = job.get("dispatch_id")
    org = job.get("org_snapshot") or {}
    employees = org.get("employees") or []
    events = []
    events.append(
        publish_event(
            r,
            run_id,
            "run.started",
            {"adapter": "crewai", "mode": "mock", "dispatch_id": dispatch_id, "protocol": "1.1"},
        )
    )
    heartbeat(r, job)

    roles = [e for e in employees if e.get("status", "active") != "paused"][:4] or [
        {"title": "Researcher", "codename": "researcher"}
    ]
    findings = []
    for e in roles:
        msg = f"{e.get('title')} (@{e.get('codename')}) analyzed: {job.get('goal')}"
        findings.append(msg)
        events.append(publish_event(r, run_id, "agent.message", {"agent": e.get("codename"), "message": msg}))
        heartbeat(r, job)
        time.sleep(0.04)

    approvals = []
    goal_l = (job.get("goal") or "").lower()
    if "deploy" in goal_l or "external" in goal_l or "outreach" in goal_l:
        tag = "external" if "outreach" in goal_l or "external" in goal_l else "deploy"
        waiting = "external" if tag == "external" else "founder"
        item = {
            "action_tag": tag,
            "title": f"Needs you: {tag}",
            "waiting_on": waiting,
            "suggested_actions": [
                {"id": "approve", "label": f"Approve {tag}", "decision": "approved"},
                {"id": "reject", "label": f"Reject {tag}", "decision": "rejected"},
            ],
            "payload": {"goal": job.get("goal")},
        }
        approvals.append(item)
        events.append(publish_event(r, run_id, "approval.needed", item))

    summary = (
        f"Crew (mock sequential) completed research-style task.\n"
        f"Goal: {job.get('goal')}\n"
        f"Findings:\n- " + "\n- ".join(findings)
    )
    max_budget = float((job.get("policy") or {}).get("max_budget_usd") or 0)
    if max_budget <= 0:
        raise RuntimeError("Hard budget limit reached — further LLM runs blocked")

    events.append(publish_event(r, run_id, "run.progress", {"percent": 100, "stage": "done"}))
    # Single terminal event
    events.append(
        publish_event(
            r,
            run_id,
            "run.finished",
            {"outcome": "succeeded", "dispatch_id": dispatch_id},
        )
    )
    return {
        "summary": summary,
        "usage": {
            "prompt_tokens": 120 * len(roles),
            "completion_tokens": 80 * len(roles),
            "cost_usd": min(0.02 * max(len(roles), 1), max_budget),
        },
        "upstream": {"framework": "crewai", "version": "mock-protocol-1.1", "mode": "mock"},
        "artifacts": [{"kind": "report", "uri": f"memory://run/{run_id}/research-report"}],
        "approvals_needed": approvals,
        "events": [{"type": e["type"], "payload": e.get("payload")} for e in events],
    }


def handle_job(job: dict[str, Any], r: redis.Redis) -> dict[str, Any]:
    run_id = job["run_id"]
    dispatch_id = job.get("dispatch_id")
    adapter = job.get("adapter") or "crewai"
    base = {
        "run_id": run_id,
        "dispatch_id": dispatch_id,
        "heartbeat_at": datetime.now(UTC).isoformat(),
        "adapter_protocol_version": 1.1,
    }
    if adapter == "metagpt":
        return {
            **base,
            "status": "failed",
            "outcome": "failed",
            "error": "MetaGPT adapter disabled",
            "usage": {},
            "upstream": {"framework": "metagpt", "version": "disabled"},
            "artifacts": [],
            "events": [{"type": "run.finished", "payload": {"outcome": "failed", "reason": "metagpt_disabled"}}],
        }

    force_mock = os.getenv("CREWAI_FORCE_MOCK", "1") == "1"
    try:
        data = run_crewai_mock(job, r) if force_mock else None
        if not force_mock:
            try:
                data = run_crewai_real(job)
            except Exception:
                data = run_crewai_mock(job, r)
        assert data is not None
        return {
            **base,
            "status": "succeeded",
            "outcome": "succeeded",
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
            **base,
            "status": "failed",
            "outcome": "failed",
            "summary": None,
            "error": str(exc),
            "usage": {},
            "upstream": {"framework": "crewai", "traceback": traceback.format_exc()[-500:]},
            "artifacts": [],
            "events": [{"type": "run.finished", "payload": {"outcome": "failed", "error": str(exc)}}],
        }


def main() -> None:
    r = client()
    print(f"[crewai-adapter] protocol=1.1 queue={JOB_QUEUE}")
    while True:
        item = r.blpop(JOB_QUEUE, timeout=5)
        if not item:
            continue
        _, raw = item
        try:
            job = json.loads(raw)
        except Exception:
            continue
        if (job.get("adapter") or "crewai") == "openhands":
            continue
        print(f"[crewai-adapter] run_id={job.get('run_id')} dispatch={job.get('dispatch_id')}")
        result = handle_job(job, r)
        r.rpush(RESULT_QUEUE, json.dumps(result))
        print(f"[crewai-adapter] terminal outcome={result.get('outcome')}")


if __name__ == "__main__":
    main()
