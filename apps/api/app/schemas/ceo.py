from typing import Any

from pydantic import BaseModel, Field


class CeoAdviseRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    company_id: str | None = None


class CeoAdviseResponse(BaseModel):
    acknowledgment: str
    plan: dict[str, Any]
    raw_markdown: str
    model_used: str | None
    stub: bool


class CeoDirectRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    company_id: str | None = None
    start_work: bool = True


class CeoDirectResponse(BaseModel):
    acknowledgment: str
    project: dict[str, Any]
    tasks: list[dict[str, Any]]
    runs_started: list[str]
    summary: dict[str, Any]
