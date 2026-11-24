import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db
from app.deps import require_membership
from app.models.employee import Employee
from app.models.user import User
from app.models.work import Approval, Budget, Project, RunEvent, Task, TaskRun
from app.schemas.work import (
    ApprovalDecide,
    ApprovalOut,
    BudgetOut,
    BudgetUpdate,
    ProjectCreate,
    ProjectOut,
    RunEventOut,
    TaskCreate,
    TaskOut,
    TaskRunOut,
)
from app.security.auth import get_current_user
from app.services.activity import activity_hub
from app.services.audit import write_audit
from app.services.orchestrator import (
    apply_worker_result,
    append_event,
    enqueue_task_run,
    ensure_company_budget,
)
from app.services.queue import EVENTS_CHANNEL_PREFIX, RESULT_QUEUE, is_budget_blocked, redis_client, set_budget_block

router = APIRouter(tags=["work"])


@router.get("/companies/{company_id}/projects", response_model=list[ProjectOut])
def list_projects(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectOut]:
    require_membership(db, company_id, user.id)
    rows = db.query(Project).filter(Project.company_id == company_id).order_by(Project.created_at.desc()).all()
    return [ProjectOut.model_validate(r) for r in rows]


@router.post("/companies/{company_id}/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    company_id: UUID,
    body: ProjectCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectOut:
    require_membership(db, company_id, user.id)
    ceo = db.query(Employee).filter(Employee.company_id == company_id, Employee.codename == "ceo").first()
    row = Project(
        company_id=company_id,
        name=body.name,
        description=body.description,
        owner_employee_id=body.owner_employee_id or (ceo.id if ceo else None),
        status="active",
    )
    db.add(row)
    ensure_company_budget(db, company_id)
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "project.created", {"name": row.name})
    return ProjectOut.model_validate(row)


@router.get("/companies/{company_id}/tasks", response_model=list[TaskOut])
def list_tasks(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TaskOut]:
    require_membership(db, company_id, user.id)
    rows = db.query(Task).filter(Task.company_id == company_id).order_by(Task.created_at.desc()).all()
    return [TaskOut.model_validate(r) for r in rows]


@router.post("/companies/{company_id}/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    company_id: UUID,
    body: TaskCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskOut:
    require_membership(db, company_id, user.id)
    project = db.get(Project, body.project_id)
    if not project or project.company_id != company_id:
        raise HTTPException(status_code=404, detail="Project not found")
    row = Task(
        company_id=company_id,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        assignee_employee_id=body.assignee_employee_id,
        priority=body.priority,
        adapter=body.adapter,
        input=body.input or {},
        status="backlog",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TaskOut.model_validate(row)


@router.post("/companies/{company_id}/tasks/{task_id}/run", response_model=TaskRunOut)
async def run_task(
    company_id: UUID,
    task_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> TaskRunOut:
    require_membership(db, company_id, user.id)
    task = db.get(Task, task_id)
    if not task or task.company_id != company_id:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        run = await enqueue_task_run(db, task=task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        action="task.run",
        actor_user_id=user.id,
        company_id=company_id,
        resource_type="task_run",
        resource_id=run.id,
        payload={"adapter": run.adapter},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return TaskRunOut.model_validate(run)


@router.get("/companies/{company_id}/runs", response_model=list[TaskRunOut])
def list_runs(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TaskRunOut]:
    require_membership(db, company_id, user.id)
    rows = (
        db.query(TaskRun)
        .filter(TaskRun.company_id == company_id)
        .order_by(TaskRun.created_at.desc())
        .limit(100)
        .all()
    )
    return [TaskRunOut.model_validate(r) for r in rows]


@router.get("/companies/{company_id}/runs/{run_id}", response_model=TaskRunOut)
def get_run(
    company_id: UUID,
    run_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskRunOut:
    require_membership(db, company_id, user.id)
    run = db.get(TaskRun, run_id)
    if not run or run.company_id != company_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return TaskRunOut.model_validate(run)


@router.get("/companies/{company_id}/runs/{run_id}/events", response_model=list[RunEventOut])
def list_run_events(
    company_id: UUID,
    run_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RunEventOut]:
    require_membership(db, company_id, user.id)
    run = db.get(TaskRun, run_id)
    if not run or run.company_id != company_id:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.seq).all()
    return [RunEventOut.model_validate(r) for r in rows]


@router.get("/companies/{company_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ApprovalOut]:
    require_membership(db, company_id, user.id)
    rows = (
        db.query(Approval)
        .filter(Approval.company_id == company_id)
        .order_by(Approval.created_at.desc())
        .all()
    )
    return [ApprovalOut.model_validate(r) for r in rows]


@router.post("/companies/{company_id}/approvals/{approval_id}/decide", response_model=ApprovalOut)
async def decide_approval(
    company_id: UUID,
    approval_id: UUID,
    body: ApprovalDecide,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalOut:
    require_membership(db, company_id, user.id)
    row = db.get(Approval, approval_id)
    if not row or row.company_id != company_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Already decided")
    row.status = body.decision
    row.decision_note = body.note
    row.decided_by_user_id = user.id
    row.decided_at = datetime.now(UTC)
    if row.run_id:
        append_event(db, row.run_id, "approval.decided", {"status": row.status, "note": body.note})
    db.commit()
    db.refresh(row)
    await activity_hub.publish(company_id, "approval.decided", {"id": str(row.id), "status": row.status})
    return ApprovalOut.model_validate(row)


@router.get("/companies/{company_id}/budget", response_model=BudgetOut)
def get_budget(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetOut:
    require_membership(db, company_id, user.id)
    row = ensure_company_budget(db, company_id)
    db.commit()
    out = BudgetOut.model_validate(row)
    out.blocked = is_budget_blocked(company_id) or float(row.spent_usd) >= float(row.hard_limit_usd)
    return out


@router.patch("/companies/{company_id}/budget", response_model=BudgetOut)
def update_budget(
    company_id: UUID,
    body: BudgetUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetOut:
    require_membership(db, company_id, user.id)
    row = ensure_company_budget(db, company_id)
    if body.soft_limit_usd is not None:
        row.soft_limit_usd = Decimal(str(body.soft_limit_usd))
    if body.hard_limit_usd is not None:
        row.hard_limit_usd = Decimal(str(body.hard_limit_usd))
    if Decimal(row.spent_usd) < Decimal(row.hard_limit_usd):
        set_budget_block(company_id, False)
    db.commit()
    db.refresh(row)
    out = BudgetOut.model_validate(row)
    out.blocked = is_budget_blocked(company_id)
    return out


@router.post("/companies/{company_id}/runs/{run_id}/cancel", response_model=TaskRunOut)
async def cancel_run(
    company_id: UUID,
    run_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskRunOut:
    require_membership(db, company_id, user.id)
    run = db.get(TaskRun, run_id)
    if not run or run.company_id != company_id:
        raise HTTPException(status_code=404, detail="Run not found")
    redis_client().set(f"aicos:run:cancel:{run_id}", "1", ex=3600)
    if run.status in ("queued", "running"):
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        append_event(db, run.id, "run.cancelled", {"by": str(user.id)})
        db.commit()
        db.refresh(run)
        await activity_hub.publish(company_id, "run.cancelled", {"run_id": str(run_id)})
    return TaskRunOut.model_validate(run)


@router.get("/features")
def features() -> dict:
    settings = get_settings()
    import shutil

    docker_ok = shutil.which("docker") is not None
    return {
        "phase": 4,
        "adapters": {
            "crewai": True,
            "metagpt": bool(getattr(settings, "metagpt_enabled", False)),
            "openhands": bool(getattr(settings, "openhands_enabled", True)),
            "ceo_stub": True,
        },
        "metagpt_status": "disabled" if not getattr(settings, "metagpt_enabled", False) else "enabled",
        "openhands_status": "stub" if not docker_ok else "docker_available",
        "docker_available": docker_ok,
    }


@router.websocket("/ws/runs/{run_id}")
async def run_events_ws(websocket: WebSocket, run_id: UUID) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    import jwt

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        run = db.get(TaskRun, run_id)
        if not run:
            await websocket.close(code=4404)
            return
        require_membership(db, run.company_id, user_id)
        events = db.query(RunEvent).filter(RunEvent.run_id == run_id).order_by(RunEvent.seq).all()
    except Exception:
        await websocket.close(code=4403)
        return
    finally:
        db.close()

    await websocket.accept()
    for ev in events:
        await websocket.send_json(
            {"type": ev.event_type, "seq": ev.seq, "payload": ev.payload, "at": ev.created_at.isoformat() if ev.created_at else None}
        )

    client = redis_client()
    pubsub = client.pubsub()
    channel = f"{EVENTS_CHANNEL_PREFIX}{run_id}"
    pubsub.subscribe(channel)
    try:
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("data"):
                try:
                    data = json.loads(msg["data"])
                except Exception:
                    data = {"raw": msg["data"]}
                await websocket.send_json(data)
            else:
                await asyncio.sleep(0.2)
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                except TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()
