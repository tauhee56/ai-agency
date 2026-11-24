from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company, Membership
from app.models.employee import Employee


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "company"
    return base[:60]


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 1
    while db.query(Company).filter(Company.slug == candidate).first():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def bootstrap_company(db: Session, *, name: str, founder_user_id: uuid.UUID) -> Company:
    company = Company(
        name=name,
        slug=unique_slug(db, name),
        founder_user_id=founder_user_id,
        status="active",
    )
    db.add(company)
    db.flush()

    membership = Membership(
        company_id=company.id,
        user_id=founder_user_id,
        rbac_role="founder",
    )
    db.add(membership)

    ceo = Employee(
        company_id=company.id,
        title="AI CEO",
        codename="ceo",
        role_prompt=(
            "You are the AI CEO of this company. Advise the Founder, coordinate "
            "departments, and keep the org chart coherent. You are the root manager."
        ),
        status="active",
        capabilities={"tools": ["plan"], "tags": ["executive", "ceo"]},
    )
    db.add(ceo)
    db.flush()

    # Opening day: seed full org automatically
    from app.services.org import seed_startup_default
    from app.models.work import Project

    seed_startup_default(db, company.id)
    welcome = Project(
        company_id=company.id,
        name="Opening day",
        description="Welcome project — your AI company is staffed and ready for direction.",
        status="active",
        owner_employee_id=ceo.id,
    )
    db.add(welcome)
    db.flush()
    return company
