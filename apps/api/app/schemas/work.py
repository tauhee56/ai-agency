from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    owner_employee_id: UUID | None = None


class ProjectOut(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str
    status: str
    owner_employee_id: UUID | None

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: UUID
    assignee_employee_id: UUID | None = None
    priority: int = 0
    adapter: str | None = "crewai"
    input: dict[str, Any] = Field(default_factory=dict)


class TaskOut(BaseModel):
    id: UUID
    company_id: UUID
    project_id: UUID
    title: str
    description: str
    status: str
    assignee_employee_id: UUID | None
    priority: int
    adapter: str | None
    input: dict[str, Any]

    model_config = {"from_attributes": True}


class TaskRunOut(BaseModel):
    id: UUID
    task_id: UUID
    company_id: UUID
    adapter: str
    status: str
    summary: str | None
    usage: dict[str, Any]
    upstream: dict[str, Any]
    error: str | None
    started_at: Any | None = None
    finished_at: Any | None = None

    model_config = {"from_attributes": True}


class RunEventOut(BaseModel):
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: Any | None = None

    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: UUID
    company_id: UUID
    run_id: UUID | None
    task_id: UUID | None
    action_tag: str
    title: str
    payload: dict[str, Any]
    status: str
    decision_note: str | None

    model_config = {"from_attributes": True}


class ApprovalDecide(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None


class BudgetOut(BaseModel):
    id: UUID
    company_id: UUID
    scope: str
    soft_limit_usd: float
    hard_limit_usd: float
    spent_usd: float
    blocked: bool = False

    model_config = {"from_attributes": True}


class BudgetUpdate(BaseModel):
    soft_limit_usd: float | None = None
    hard_limit_usd: float | None = None
