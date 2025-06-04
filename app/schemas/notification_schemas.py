from pydantic import BaseModel
from uuid import UUID
from typing import List, Dict, Any

class NotificationSchema(BaseModel):
    notification_id: UUID
    title: str
    content: str
    create_time: Any
    is_read: bool

class NotificationListResponse(BaseModel):
    notifications: List[NotificationSchema]
    total_count: int

class NotificationActionResponse(BaseModel):
    success: bool
    message: str

    class Config:
        from_attributes = True