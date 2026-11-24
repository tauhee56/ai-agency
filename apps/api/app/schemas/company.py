from uuid import UUID

from pydantic import BaseModel, Field


class CompanyOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    founder_user_id: UUID

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MembershipOut(BaseModel):
    id: UUID
    company_id: UUID
    user_id: UUID
    rbac_role: str
    company: CompanyOut

    model_config = {"from_attributes": True}
