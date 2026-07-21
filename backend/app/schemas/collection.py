from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    name: str
    description: str | None
    created_at: datetime
