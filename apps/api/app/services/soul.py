"""Employee Soul Markdown ↔ role_prompt + pinned memories (Orca M4 pattern)."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.memory import Memory

SOUL_HEADER = "# SOUL"
MEMORY_HEADER = "# MEMORY (pinned)"


def export_soul(db: Session, employee: Employee) -> str:
    pinned = (
        db.query(Memory)
        .filter(
            Memory.company_id == employee.company_id,
            Memory.scope == "employee",
            Memory.scope_id == employee.id,
            Memory.kind.in_(["fact", "procedure", "decision"]),
        )
        .order_by(Memory.created_at.desc())
        .limit(20)
        .all()
    )
    mem_block = "\n".join(f"- ({m.kind}) {m.content}" for m in pinned) or "- (none)"
    return (
        f"{SOUL_HEADER}\n"
        f"title: {employee.title}\n"
        f"codename: {employee.codename}\n"
        f"status: {employee.status}\n\n"
        f"## Role\n{employee.role_prompt.strip() or '(empty)'}\n\n"
        f"{MEMORY_HEADER}\n{mem_block}\n"
    )


def import_soul(db: Session, employee: Employee, markdown: str) -> dict:
    role = employee.role_prompt
    # Extract ## Role section
    m = re.search(r"##\s*Role\s*\n([\s\S]*?)(?=\n#|\Z)", markdown)
    if m:
        role = m.group(1).strip()
        if role == "(empty)":
            role = ""
    employee.role_prompt = role

    # Replace pinned employee memories from MEMORY section bullets
    mem_m = re.search(r"#\s*MEMORY[^\n]*\n([\s\S]*)", markdown, re.I)
    created = 0
    if mem_m:
        db.query(Memory).filter(
            Memory.company_id == employee.company_id,
            Memory.scope == "employee",
            Memory.scope_id == employee.id,
        ).delete()
        for line in mem_m.group(1).splitlines():
            line = line.strip()
            if not line.startswith("-") or "(none)" in line:
                continue
            kind = "fact"
            km = re.match(r"-\s*\((\w+)\)\s*(.*)", line)
            if km:
                kind = km.group(1)
                content = km.group(2).strip()
            else:
                content = line.lstrip("- ").strip()
            if not content:
                continue
            db.add(
                Memory(
                    company_id=employee.company_id,
                    scope="employee",
                    scope_id=employee.id,
                    kind=kind if kind in ("fact", "procedure", "decision", "episode") else "fact",
                    content=content[:4000],
                )
            )
            created += 1
    db.flush()
    return {"role_prompt_len": len(employee.role_prompt or ""), "pinned_memories": created}


def tidy_employee_soul(db: Session, employee_id: UUID) -> dict | None:
    """Nightly-style tidy: summarize role_prompt length only (no tools)."""
    emp = db.get(Employee, employee_id)
    if not emp:
        return None
    text = (emp.role_prompt or "").strip()
    if len(text) > 1200:
        emp.role_prompt = text[:1100].rstrip() + "\n\n(…tidied; full history in memories)"
        db.add(
            Memory(
                company_id=emp.company_id,
                scope="employee",
                scope_id=emp.id,
                kind="procedure",
                content=f"Soul tidy truncated role_prompt from {len(text)} chars.",
            )
        )
        db.flush()
        return {"tidied": True, "employee_id": str(emp.id)}
    return {"tidied": False, "employee_id": str(emp.id)}
