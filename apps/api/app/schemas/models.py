from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Provider = Literal["openai", "anthropic", "gemini", "compatible", "local"]


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Provider
    model_name: str = Field(min_length=1, max_length=120)
    base_url: str | None = None
    api_key: str | None = Field(default=None, max_length=4096)
    is_default: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: Provider | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = None
    api_key: str | None = Field(default=None, max_length=4096)
    is_default: bool | None = None
    extra: dict[str, Any] | None = None


class ModelConfigOut(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    provider: str
    model_name: str
    base_url: str | None
    is_default: bool
    has_api_key: bool
    extra: dict[str, Any]

    model_config = {"from_attributes": True}
