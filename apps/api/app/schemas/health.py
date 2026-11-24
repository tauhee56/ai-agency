from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db: bool
    redis: bool
    version: str = "0.1.0-phase1"
