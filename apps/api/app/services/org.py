from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee import Employee
from app.schemas.org import EmployeeOut, OrgChartNode

# Seed templates — department + role catalog
STARTUP_DEFAULT = {
    "departments": [
        {"name": "Executive", "description": "Founder office and AI CEO"},
        {"name": "Engineering", "description": "Product engineering and platform"},
        {"name": "Product", "description": "Product strategy and roadmap"},
        {"name": "Research", "description": "Market and technical research"},
        {"name": "Operations", "description": "Ops, content, and outreach"},
    ],
    "employees": [
        {
            "title": "CTO",
            "codename": "cto",
            "department": "Engineering",
            "manager": "ceo",
            "role_prompt": "You lead engineering. Break work into shippable tasks and enforce quality.",
            "capabilities": {"tools": ["code_review", "plan"], "tags": ["engineering", "lead"]},
            "adapter_pref": "crewai",
        },
        {
            "title": "Staff Engineer",
            "codename": "eng-staff",
            "department": "Engineering",
            "manager": "cto",
            "role_prompt": "You implement features and write clear technical notes.",
            "capabilities": {"tools": ["code_exec", "search"], "tags": ["engineering"]},
            "adapter_pref": "openhands",
        },
        {
            "title": "Product Manager",
            "codename": "pm",
            "department": "Product",
            "manager": "ceo",
            "role_prompt": "You clarify requirements, prioritize, and write crisp specs.",
            "capabilities": {"tools": ["search", "write"], "tags": ["product"]},
            "adapter_pref": "crewai",
        },
        {
            "title": "Researcher",
            "codename": "researcher",
            "department": "Research",
            "manager": "ceo",
            "role_prompt": "You research markets and tech, cite sources, and summarize tradeoffs.",
            "capabilities": {"tools": ["search"], "tags": ["research"]},
            "adapter_pref": "crewai",
        },
        {
            "title": "Content Lead",
            "codename": "content",
            "department": "Operations",
            "manager": "ceo",
            "role_prompt": "You draft content and outreach that match brand voice.",
            "capabilities": {"tools": ["write", "external"], "tags": ["ops", "content"]},
            "adapter_pref": "crewai",
        },
        {
            "title": "Ops Analyst",
            "codename": "ops",
            "department": "Operations",
            "manager": "ceo",
            "role_prompt": "You produce ops reports and KPI summaries.",
            "capabilities": {"tools": ["write"], "tags": ["ops"]},
            "adapter_pref": "crewai",
        },
    ],
}


def build_org_chart(employees: list[Employee]) -> list[OrgChartNode]:
    by_id = {e.id: e for e in employees}
    children: dict[UUID | None, list[Employee]] = {}
    for e in employees:
        children.setdefault(e.manager_employee_id, []).append(e)

    def walk(emp: Employee) -> OrgChartNode:
        kids = sorted(children.get(emp.id, []), key=lambda x: x.title)
        return OrgChartNode(
            employee=EmployeeOut.model_validate(emp),
            reports=[walk(c) for c in kids],
        )

    roots = children.get(None, [])
    # Prefer CEO as single root when present
    ceo = next((e for e in roots if e.codename == "ceo"), None)
    if ceo:
        return [walk(ceo)] + [walk(e) for e in roots if e.id != ceo.id]
    return [walk(e) for e in sorted(roots, key=lambda x: x.title)]


def seed_startup_default(db: Session, company_id: UUID) -> dict:
    existing_depts = db.query(Department).filter(Department.company_id == company_id).all()
    dept_by_name = {d.name: d for d in existing_depts}

    for spec in STARTUP_DEFAULT["departments"]:
        if spec["name"] not in dept_by_name:
            d = Department(
                company_id=company_id,
                name=spec["name"],
                description=spec["description"],
            )
            db.add(d)
            db.flush()
            dept_by_name[d.name] = d

    employees = db.query(Employee).filter(Employee.company_id == company_id).all()
    by_code = {e.codename: e for e in employees}
    ceo = by_code.get("ceo")
    if ceo is None:
        ceo = Employee(
            company_id=company_id,
            title="AI CEO",
            codename="ceo",
            role_prompt="You are the AI CEO. Coordinate departments and report to the Founder.",
            status="active",
            capabilities={"tools": ["plan"], "tags": ["executive", "ceo"]},
            department_id=dept_by_name.get("Executive").id if dept_by_name.get("Executive") else None,
        )
        db.add(ceo)
        db.flush()
        by_code["ceo"] = ceo
    else:
        if dept_by_name.get("Executive") and not ceo.department_id:
            ceo.department_id = dept_by_name["Executive"].id
        caps = dict(ceo.capabilities or {})
        caps.setdefault("tags", ["executive", "ceo"])
        caps.setdefault("tools", ["plan"])
        ceo.capabilities = caps
        ceo.role_prompt = ceo.role_prompt or (
            "You are the AI CEO. Coordinate departments and report to the Founder."
        )

    created = 0
    for spec in STARTUP_DEFAULT["employees"]:
        if spec["codename"] in by_code:
            continue
        manager = by_code.get(spec["manager"])
        dept = dept_by_name.get(spec["department"])
        emp = Employee(
            company_id=company_id,
            title=spec["title"],
            codename=spec["codename"],
            role_prompt=spec["role_prompt"],
            department_id=dept.id if dept else None,
            manager_employee_id=manager.id if manager else ceo.id,
            adapter_pref=spec.get("adapter_pref"),
            status="active",
            capabilities=spec.get("capabilities") or {},
        )
        db.add(emp)
        db.flush()
        by_code[emp.codename] = emp
        created += 1

    # Wire Engineering lead
    eng = dept_by_name.get("Engineering")
    cto = by_code.get("cto")
    if eng and cto:
        eng.lead_employee_id = cto.id
    exec_dept = dept_by_name.get("Executive")
    if exec_dept:
        exec_dept.lead_employee_id = ceo.id

    db.flush()
    return {
        "departments": len(dept_by_name),
        "employees": len(by_code),
        "created_employees": created,
    }
