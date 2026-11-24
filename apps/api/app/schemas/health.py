from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db: bool
    redis: bool
    version: str = "0.3.0-phase3"
