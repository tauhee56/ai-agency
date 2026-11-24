from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_membership
from app.models.employee import Employee
from app.models.memory import Memory
from app.models.user import User
from app.models.work import Artifact, Project, Task, TaskRun, UsageRecord
from app.security.auth import get_current_user
from app.services.activity import activity_hub
from app.services.audit import write_audit
from app.services.orchestrator import enqueue_task_run
from app.services.playbooks import PLAYBOOKS, get_playbook

router = APIRouter(tags=["ops"])


class MemoryCreate(BaseModel):
    scope: str = "company"
    scope_id: UUID | None = None
    kind: str = "fact"
    content: str = Field(min_length=1, max_length=8000)
    source_run_id: UUID | None = None


class MemoryOut(BaseModel):
    id: UUID
    company_id: UUID
    scope: str
    kind: str
    content: str
    source_run_id: UUID | None

    model_config = {"from_attributes": True}


class PlaybookRunRequest(BaseModel):
    playbook_id: str
    goal: str = Field(min_length=1, max_length=500)
    project_name: str | None = None


class IntegrationDraft(BaseModel):
    channel: str = Field(pattern="^(email|slack|notion)$")
    subject: str = ""
    body: str = Field(min_length=1, max_length=8000)


@router.get("/companies/{company_id}/playbooks")
def list_playbooks(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    require_membership(db, company_id, user.id)
    return PLAYBOOKS


@router.post("/companies/{company_id}/playbooks/run")
async def run_playbook(
    company_id: UUID,
    body: PlaybookRunRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    require_membership(db, company_id, user.id)
    pb = get_playbook(body.playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if pb.get("requires_metagpt"):
        raise HTTPException(status_code=400, detail="Playbook requires MetaGPT (disabled)")

    project = Project(
        company_id=company_id,
        name=body.project_name or f"Playbook: {pb['name']}",
        description=pb["description"],
        status="active",
    )
    db.add(project)
    db.flush()

    emp = (
        db.query(Employee)
        .filter(Employee.company_id == company_id, Employee.codename == pb["task_graph"][0].get("role"))
        .first()
    )
    task = Task(
        company_id=company_id,
        project_id=project.id,
        title=f"{pb['name']}: {body.goal}",
        description=pb["description"] + "\n\n" + " → ".join(t["title"] for t in pb["task_graph"]),
        assignee_employee_id=emp.id if emp else None,
        adapter=pb.get("adapter") or "crewai",
        input={"playbook_id": pb["id"], "goal": body.goal, "task_graph": pb["task_graph"]},
        status="backlog",
    )
    db.add(task)
    db.flush()

    # Seed memory intent
    mem = Memory(
        company_id=company_id,
        scope="project",
        scope_id=project.id,
        kind="procedure",
        content=f"Started playbook {pb['id']} with goal: {body.goal}",
    )
    db.add(mem)
    db.commit()

    try:
        run = await enqueue_task_run(db, task=task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    write_audit(
        db,
        action="playbook.run",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="task_run",
        resource_id=run.id,
        payload={"playbook_id": pb["id"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    await activity_hub.publish(company_id, "playbook.started", {"playbook_id": pb["id"], "run_id": str(run.id)})
    return {
        "project_id": str(project.id),
        "task_id": str(task.id),
        "run_id": str(run.id),
        "playbook_id": pb["id"],
        "memory_id": str(mem.id),
    }


@router.get("/companies/{company_id}/memories", response_model=list[MemoryOut])
def list_memories(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MemoryOut]:
    require_membership(db, company_id, user.id)
    rows = db.query(Memory).filter(Memory.company_id == company_id).order_by(Memory.created_at.desc()).limit(200).all()
    return [MemoryOut.model_validate(r) for r in rows]


@router.post("/companies/{company_id}/memories", response_model=MemoryOut, status_code=201)
async def create_memory(
    company_id: UUID,
    body: MemoryCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MemoryOut:
    require_membership(db, company_id, user.id)
    row = Memory(
        company_id=company_id,
        scope=body.scope,
        scope_id=body.scope_id,
        kind=body.kind,
        content=body.content,
        source_run_id=body.source_run_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return MemoryOut.model_validate(row)


@router.post("/companies/{company_id}/integrations/draft")
async def integration_draft(
    company_id: UUID,
    body: IntegrationDraft,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Draft-only integration — does not send externally without approval."""
    require_membership(db, company_id, user.id)
    from app.models.work import Approval

    approval = Approval(
        company_id=company_id,
        action_tag="external",
        title=f"Approve {body.channel} send",
        payload={"channel": body.channel, "subject": body.subject, "body": body.body[:2000]},
        status="pending",
    )
    db.add(approval)
    mem = Memory(
        company_id=company_id,
        scope="company",
        kind="decision",
        content=f"Drafted {body.channel} message pending Founder approval: {body.subject or body.body[:80]}",
    )
    db.add(mem)
    db.commit()
    db.refresh(approval)
    await activity_hub.publish(company_id, "integration.drafted", {"channel": body.channel, "approval_id": str(approval.id)})
    return {"status": "pending_approval", "approval_id": str(approval.id), "memory_id": str(mem.id)}


@router.get("/companies/{company_id}/kpis")
def kpis(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    require_membership(db, company_id, user.id)
    runs = db.query(TaskRun).filter(TaskRun.company_id == company_id).all()
    by_status: dict[str, int] = {}
    for r in runs:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    spend = (
        db.query(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
        .filter(UsageRecord.company_id == company_id)
        .scalar()
    )
    artifacts = db.query(Artifact).filter(Artifact.company_id == company_id).count()
    memories = db.query(Memory).filter(Memory.company_id == company_id).count()
    return {
        "runs_total": len(runs),
        "runs_by_status": by_status,
        "spend_usd": float(spend or 0),
        "artifacts": artifacts,
        "memories": memories,
        "throughput_succeeded": by_status.get("succeeded", 0),
    }
