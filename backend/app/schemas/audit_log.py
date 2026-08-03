from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: str | None
    detail: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogRead]
    total: int
