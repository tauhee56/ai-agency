from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.company import Company
from app.models.memory import Memory
from app.models.schedule import PlaybookSchedule
from app.models.work import Approval
from app.services.approvals_meta import suggested_actions_for, waiting_on_for
from app.services.audit import write_audit
from app.services.scheduler import fire_schedule
from app.services.webhook_hygiene import connector_defaults, wrap_inbound_as_data

router = APIRouter(prefix="/hooks", tags=["webhooks"])


@router.get("/connectors/defaults")
def connector_policy_defaults() -> dict[str, Any]:
    return {
        "email": connector_defaults("email"),
        "slack": connector_defaults("slack"),
        "notion": connector_defaults("notion"),
        "webhook": connector_defaults("webhook"),
        "policy": "draft_first",
        "note": "Inbound bodies are never treated as instructions; sends require Founder approval.",
    }


@router.post("/inbound/{company_id}")
async def inbound_webhook(
    company_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_aicos_hook_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    settings = get_settings()
    expected = getattr(settings, "webhook_shared_secret", None) or "dev-webhook-secret"
    if x_aicos_hook_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        raw = await request.json()
    except Exception:
        raw = (await request.body()).decode("utf-8", errors="replace")

    wrapped = wrap_inbound_as_data(raw, source="webhook")
    # Audit raw separately (truncated) — not fed to model as instructions
    write_audit(
        db,
        action="webhook.inbound",
        company_id=company_id,
        resource_type="webhook",
        payload={
            "raw_preview": str(raw)[:1500],
            "injection_flagged": wrapped["injection_flagged"],
            "wrapped_role": wrapped["role"],
        },
        ip=request.client.host if request.client else None,
    )

    # Draft-first: create approval for any actionable inbound
    waiting = waiting_on_for("external", {"waiting_on": "external"})
    approval = Approval(
        company_id=company_id,
        action_tag="external",
        title="Needs you: inbound webhook draft",
        payload={"wrapped": wrapped, "connector": connector_defaults("webhook")},
        waiting_on=waiting,
        suggested_actions=suggested_actions_for("external", waiting),
        status="pending",
    )
    db.add(approval)
    db.add(
        Memory(
            company_id=company_id,
            scope="company",
            kind="episode",
            content=f"Inbound webhook received (flagged={wrapped['injection_flagged']}). Draft only.",
        )
    )

    # Optional: fire webhook-triggered schedules (still draft/enqueue playbook; not auto-send)
    fired = []
    schedules = (
        db.query(PlaybookSchedule)
        .filter(
            PlaybookSchedule.company_id == company_id,
            PlaybookSchedule.trigger == "webhook",
            PlaybookSchedule.enabled.is_(True),
        )
        .all()
    )
    db.commit()
    for sched in schedules:
        try:
            res = await fire_schedule(db, sched)
            if res:
                fired.append(res)
        except Exception:
            pass

    db.refresh(approval)
    return {
        "status": "accepted_as_data",
        "approval_id": str(approval.id),
        "injection_flagged": wrapped["injection_flagged"],
        "connector_policy": "draft_first",
        "schedules_fired": fired,
    }
