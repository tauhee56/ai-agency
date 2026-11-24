"""AI CEO directs the company: natural language → projects, tasks, assignments."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee import Employee
from app.models.work import Project, Task
from app.services.activity import activity_hub
from app.services.orchestrator import enqueue_task_run


DEPT_KEYWORDS = [
    (("research", "market", "competitor", "landscape", "tam"), "researcher", "Research"),
    (("engineer", "code", "build", "implement", "ship", "sandbox"), "eng-staff", "Engineering"),
    (("product", "roadmap", "spec", "priorit"), "pm", "Product"),
    (("content", "blog", "outreach", "marketing", "write"), "content", "Operations"),
    (("ops", "report", "kpi", "metric"), "ops", "Operations"),
]


def _pick_assignee(db: Session, company_id: UUID, text: str) -> tuple[Employee | None, str | None]:
    lower = text.lower()
    by_code = {
        e.codename: e
        for e in db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "active").all()
    }
    for keys, codename, dept in DEPT_KEYWORDS:
        if any(k in lower for k in keys):
            return by_code.get(codename), dept
    # default: researcher or ceo
    return by_code.get("researcher") or by_code.get("pm") or by_code.get("ceo"), None


def _project_title(message: str) -> str:
    quoted = re.search(r"[\"“](.+?)[\"”]", message)
    if quoted:
        return quoted.group(1).strip()[:120]
    m = re.search(r"(?:project|initiative|program)\s+(?:called\s+|named\s+)?[\"']?([^\"'.\n]{3,80})", message, re.I)
    if m:
        return m.group(1).strip()[:120]
    # First sentence fragment
    first = re.split(r"[.!\n]", message.strip())[0].strip()
    if len(first) > 8:
        return (first[:90] + ("…" if len(first) > 90 else "")).lstrip("Please ").lstrip("please ")
    return "Founder initiative"


def _task_ideas(message: str, project_title: str) -> list[str]:
    ideas: list[str] = []
    # Bullet lines
    for line in message.splitlines():
        s = line.strip()
        if re.match(r"^[-*•]\s+", s) or re.match(r"^\d+[.)]\s+", s):
            ideas.append(re.sub(r"^[-*•\d.)\s]+", "", s)[:160])
    if ideas:
        return ideas[:5]
    # Heuristic split into company workstreams
    base = project_title.rstrip(".")
    return [
        f"Clarify goals for {base}",
        f"Research and brief on {base}",
        f"Draft execution plan for {base}",
        f"Identify risks and open questions for {base}",
    ][:4]


async def ceo_direct_company(
    db: Session,
    *,
    company_id: UUID,
    message: str,
    start_work: bool = True,
) -> dict[str, Any]:
    ceo = (
        db.query(Employee)
        .filter(Employee.company_id == company_id, Employee.codename == "ceo")
        .first()
    )
    title = _project_title(message)
    project = Project(
        company_id=company_id,
        name=title,
        description=message[:2000],
        status="active",
        owner_employee_id=ceo.id if ceo else None,
    )
    db.add(project)
    db.flush()

    created_tasks: list[dict[str, Any]] = []
    for idea in _task_ideas(message, title):
        assignee, dept_hint = _pick_assignee(db, company_id, idea + " " + message)
        dept = None
        if dept_hint:
            dept = (
                db.query(Department)
                .filter(Department.company_id == company_id, Department.name == dept_hint)
                .first()
            )
        task = Task(
            company_id=company_id,
            project_id=project.id,
            title=idea,
            description=f"Assigned by AI CEO from Founder direction.\n\nContext:\n{message[:1500]}",
            status="ready",
            assignee_employee_id=assignee.id if assignee else None,
            adapter="crewai",
            input={
                "directed_by": "ceo",
                "department": dept.name if dept else dept_hint,
                "founder_message": message[:500],
            },
            priority=1,
        )
        db.add(task)
        db.flush()
        created_tasks.append(
            {
                "id": str(task.id),
                "title": task.title,
                "assignee": assignee.title if assignee else None,
                "assignee_codename": assignee.codename if assignee else None,
                "department": dept.name if dept else dept_hint,
            }
        )

    db.commit()

    runs_started: list[str] = []
    if start_work:
        for tmeta in created_tasks[:2]:
            task = db.get(Task, UUID(tmeta["id"]))
            if not task:
                continue
            try:
                run = await enqueue_task_run(db, task=task)
                runs_started.append(str(run.id))
                await activity_hub.publish(
                    company_id,
                    "employee.started_work",
                    {
                        "who": tmeta.get("assignee") or "Team",
                        "task": tmeta["title"],
                        "project": title,
                    },
                )
            except ValueError:
                # budget etc. — still leave tasks ready
                pass

    await activity_hub.publish(
        company_id,
        "ceo.directed",
        {
            "project": title,
            "tasks": len(created_tasks),
            "message": "AI CEO stood up a project and put people to work",
        },
    )

    ack = (
        f"Understood. I've opened project “{title}” and put "
        f"{len(created_tasks)} workstreams with the team"
        + (f"; {len(runs_started)} already underway." if runs_started else ".")
    )
    return {
        "acknowledgment": ack,
        "project": {"id": str(project.id), "name": project.name},
        "tasks": created_tasks,
        "runs_started": runs_started,
        "summary": {
            "people_assigned": sorted({t["assignee"] for t in created_tasks if t.get("assignee")}),
            "departments": sorted({t["department"] for t in created_tasks if t.get("department")}),
        },
    }
