from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.department import Department
from app.models.employee import Employee
from app.models.model_config import ModelConfig
from app.models.work import Approval, Budget, Project, RunEvent, Task, TaskRun, UsageRecord
from app.security.crypto import decrypt_secret
from app.services.activity import activity_hub
from app.services.queue import enqueue_job, is_budget_blocked, set_budget_block


def ensure_company_budget(db: Session, company_id: UUID) -> Budget:
    row = (
        db.query(Budget)
        .filter(Budget.company_id == company_id, Budget.scope == "company")
        .first()
    )
    if row:
        return row
    row = Budget(
        company_id=company_id,
        scope="company",
        soft_limit_usd=Decimal("10"),
        hard_limit_usd=Decimal("25"),
        spent_usd=Decimal("0"),
    )
    db.add(row)
    db.flush()
    return row


def check_budget_or_raise(db: Session, company_id: UUID) -> Budget:
    budget = ensure_company_budget(db, company_id)
    if Decimal(budget.spent_usd) >= Decimal(budget.hard_limit_usd) or is_budget_blocked(company_id):
        set_budget_block(company_id, True)
        raise ValueError("Hard budget limit reached — further LLM runs blocked")
    return budget


def record_usage(
    db: Session,
    *,
    company_id: UUID,
    run_id: UUID | None,
    cost_usd: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    model_config_id: UUID | None = None,
) -> None:
    budget = ensure_company_budget(db, company_id)
    budget.spent_usd = Decimal(budget.spent_usd) + Decimal(str(cost_usd))
    db.add(
        UsageRecord(
            company_id=company_id,
            run_id=run_id,
            model_config_id=model_config_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=Decimal(str(cost_usd)),
        )
    )
    if Decimal(budget.spent_usd) >= Decimal(budget.hard_limit_usd):
        set_budget_block(company_id, True)
    db.flush()


def next_event_seq(db: Session, run_id: UUID) -> int:
    last = db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.seq.desc()).first()
    return (last.seq + 1) if last else 1


def append_event(db: Session, run_id: UUID, event_type: str, payload: dict[str, Any] | None = None) -> RunEvent:
    ev = RunEvent(
        run_id=run_id,
        seq=next_event_seq(db, run_id),
        event_type=event_type,
        payload=payload or {},
    )
    db.add(ev)
    db.flush()
    return ev


def build_org_snapshot(db: Session, company_id: UUID) -> dict[str, Any]:
    employees = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "active").all()
    departments = db.query(Department).filter(Department.company_id == company_id).all()
    return {
        "employees": [
            {
                "id": str(e.id),
                "title": e.title,
                "codename": e.codename,
                "role_prompt": e.role_prompt,
                "model_id": str(e.model_config_id) if e.model_config_id else None,
                "manager_employee_id": str(e.manager_employee_id) if e.manager_employee_id else None,
                "capabilities": e.capabilities or {},
                "adapter_pref": e.adapter_pref,
            }
            for e in employees
        ],
        "departments": [
            {
                "id": str(d.id),
                "name": d.name,
                "lead_employee_id": str(d.lead_employee_id) if d.lead_employee_id else None,
            }
            for d in departments
        ],
    }


def model_bindings(db: Session, company_id: UUID) -> list[dict[str, Any]]:
    rows = db.query(ModelConfig).filter(ModelConfig.company_id == company_id).all()
    out = []
    for r in rows:
        key = None
        if r.api_key_encrypted:
            try:
                key = decrypt_secret(r.api_key_encrypted)
            except ValueError:
                key = None
        out.append(
            {
                "model_id": str(r.id),
                "provider": r.provider,
                "model_name": r.model_name,
                "base_url": r.base_url,
                "api_key": key,
                "is_default": r.is_default,
                "extra": r.extra or {},
            }
        )
    return out


async def enqueue_task_run(
    db: Session,
    *,
    task: Task,
    adapter: str | None = None,
) -> TaskRun:
    settings = get_settings()
    chosen = adapter or task.adapter or "crewai"
    if chosen == "metagpt" and not getattr(settings, "metagpt_enabled", False):
        raise ValueError("MetaGPT adapter is disabled (set METAGPT_ENABLED=true to enable optional worker)")
    if chosen == "openhands" and not getattr(settings, "openhands_enabled", True):
        raise ValueError("OpenHands adapter is disabled")

    check_budget_or_raise(db, task.company_id)

    run = TaskRun(
        id=uuid4(),
        task_id=task.id,
        company_id=task.company_id,
        adapter=chosen,
        status="queued",
    )
    db.add(run)
    task.status = "ready"
    db.flush()
    append_event(db, run.id, "run.queued", {"adapter": chosen})

    project = db.get(Project, task.project_id)
    budget = ensure_company_budget(db, task.company_id)
    remaining = float(Decimal(budget.hard_limit_usd) - Decimal(budget.spent_usd))

    job = {
        "adapter_protocol_version": 1,
        "job_id": str(uuid4()),
        "company_id": str(task.company_id),
        "project_id": str(task.project_id),
        "task_id": str(task.id),
        "run_id": str(run.id),
        "adapter": chosen,
        "goal": task.title,
        "inputs": {
            "description": task.description,
            **(task.input or {}),
            "project_name": project.name if project else None,
        },
        "org_snapshot": build_org_snapshot(db, task.company_id),
        "model_bindings": model_bindings(db, task.company_id),
        "policy": {
            "max_budget_usd": max(remaining, 0),
            "timeout_sec": 1800,
            "allowed_tools": ["search", "write"],
            "require_approval_for": ["external", "payment", "deploy", "destructive"],
        },
        "callback": {
            "events_ws_channel": f"run:{run.id}",
            "result_queue": "aicos:results",
        },
    }
    enqueue_job(job)
    db.commit()
    await activity_hub.publish(task.company_id, "run.queued", {"run_id": str(run.id), "adapter": chosen})
    return run


def apply_worker_result(db: Session, result: dict[str, Any]) -> TaskRun | None:
    run_id = UUID(result["run_id"])
    run = db.get(TaskRun, run_id)
    if not run:
        return None
    run.status = result.get("status", "failed")
    run.summary = result.get("summary")
    run.usage = result.get("usage") or {}
    run.upstream = result.get("upstream") or {}
    run.error = result.get("error")
    run.finished_at = datetime.now(UTC)
    if not run.started_at:
        run.started_at = run.finished_at

    task = db.get(Task, run.task_id)
    if task:
        task.status = "done" if run.status == "succeeded" else "failed"

    cost = float((run.usage or {}).get("cost_usd") or 0)
    if cost:
        record_usage(
            db,
            company_id=run.company_id,
            run_id=run.id,
            cost_usd=cost,
            prompt_tokens=int((run.usage or {}).get("prompt_tokens") or 0),
            completion_tokens=int((run.usage or {}).get("completion_tokens") or 0),
        )

    # Sensitive tool simulation → approval if requested
    for art in result.get("artifacts") or []:
        from app.models.work import Artifact

        db.add(
            Artifact(
                company_id=run.company_id,
                run_id=run.id,
                task_id=run.task_id,
                kind=art.get("kind") or "report",
                uri=art.get("uri") or "",
                meta=art,
            )
        )

    for pending in result.get("approvals_needed") or []:
        db.add(
            Approval(
                company_id=run.company_id,
                run_id=run.id,
                task_id=run.task_id,
                action_tag=pending.get("action_tag") or "external",
                title=pending.get("title") or "Approval required",
                payload=pending.get("payload") or {},
                status="pending",
            )
        )

    append_event(db, run.id, f"run.{run.status}", {"summary": run.summary})

    # Memory writeback for completed playbooks / research runs
    if run.status == "succeeded" and run.summary:
        from app.models.memory import Memory

        task_input = (task.input if task else {}) or {}
        kind = "fact"
        if task_input.get("playbook_id"):
            kind = "decision"
        db.add(
            Memory(
                company_id=run.company_id,
                scope="task" if task else "company",
                scope_id=task.id if task else None,
                kind=kind,
                content=run.summary[:4000],
                source_run_id=run.id,
            )
        )

    db.commit()
    return run
