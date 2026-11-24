from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_membership
from app.models.audit import AuditEvent
from app.models.user import User
from app.security.auth import get_current_user

router = APIRouter(tags=["admin"])


@router.get("/companies/{company_id}/audit/export")
def export_audit(
    company_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    require_membership(db, company_id, user.id)
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.company_id == company_id)
        .order_by(AuditEvent.id.asc())
        .all()
    )

    def gen():
        yield "id,action,actor_user_id,resource_type,resource_id,created_at,payload\n"
        for r in rows:
            payload = str(r.payload).replace('"', "'").replace("\n", " ")
            yield (
                f"{r.id},{r.action},{r.actor_user_id},{r.resource_type},{r.resource_id},"
                f"{r.created_at},\"{payload}\"\n"
            )

    return StreamingResponse(gen(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=audit-{company_id}.csv"
    })


@router.get("/security/checklist")
def security_checklist() -> dict[str, Any]:
    return {
        "phase": 6,
        "items": [
            {"id": "rls", "status": "documented", "note": "SQL template in docs/sql/rls_template.sql — apply in prod"},
            {"id": "rate_limits", "status": "enabled", "note": "120 req/min/IP middleware"},
            {"id": "secrets", "status": "partial", "note": "Fernet ENCRYPTION_KEY; rotate by re-encrypt job (documented)"},
            {"id": "audit_export", "status": "enabled", "note": "CSV export endpoint"},
            {"id": "headers", "status": "enabled", "note": "nosniff, frame deny, referrer"},
            {"id": "docker_sandboxes", "status": "blocked", "note": "No Docker on this VM"},
            {"id": "load_test", "status": "smoke", "note": "scripts/smoke_load.sh lightweight"},
            {"id": "licenses", "status": "enabled", "note": "NOTICE / THIRD_PARTY_LICENSES.md"},
        ],
    }


@router.get("/security/runbook", response_class=PlainTextResponse)
def runbook() -> str:
    return (
        "AI Company OS — ops runbook (Phase 6)\n"
        "1. Backup: pg_dump aicos > backup.sql ; redis-cli BGSAVE\n"
        "2. Restore: psql aicos < backup.sql\n"
        "3. Rotate ENCRYPTION_KEY: set new key, re-encrypt model_configs via admin job, restart API\n"
        "4. Rotate JWT_SECRET: forces re-login\n"
        "5. Kill hung run: POST /companies/{id}/runs/{run_id}/cancel\n"
        "6. Budget emergency stop: PATCH budget hard_limit_usd to spent_usd\n"
        "7. Disable MetaGPT/OpenHands via METAGPT_ENABLED / OPENHANDS_ENABLED\n"
    )
