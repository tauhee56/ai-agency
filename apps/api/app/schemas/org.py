from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EmployeeStatus = Literal["active", "paused", "retired"]
AdapterPref = Literal["crewai", "metagpt", "openhands"] | None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    parent_department_id: UUID | None = None
    lead_employee_id: UUID | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    parent_department_id: UUID | None = None
    lead_employee_id: UUID | None = None


class DepartmentOut(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str
    parent_department_id: UUID | None
    lead_employee_id: UUID | None

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    codename: str = Field(min_length=1, max_length=80)
    role_prompt: str = ""
    department_id: UUID | None = None
    manager_employee_id: UUID | None = None
    model_config_id: UUID | None = None
    adapter_pref: str | None = None
    status: EmployeeStatus = "active"
    capabilities: dict[str, Any] = Field(default_factory=dict)


class EmployeeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    role_prompt: str | None = None
    department_id: UUID | None = None
    manager_employee_id: UUID | None = None
    model_config_id: UUID | None = None
    adapter_pref: str | None = None
    status: EmployeeStatus | None = None
    capabilities: dict[str, Any] | None = None


class EmployeeOut(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    codename: str
    role_prompt: str
    department_id: UUID | None
    manager_employee_id: UUID | None
    model_config_id: UUID | None
    adapter_pref: str | None
    status: str
    capabilities: dict[str, Any]

    model_config = {"from_attributes": True}


class OrgChartNode(BaseModel):
    employee: EmployeeOut
    reports: list["OrgChartNode"] = Field(default_factory=list)


class OrgSnapshot(BaseModel):
    departments: list[DepartmentOut]
    employees: list[EmployeeOut]
    chart: list[OrgChartNode]
    ceo: EmployeeOut | None


class SeedTemplateRequest(BaseModel):
    template: Literal["startup_default"] = "startup_default"
