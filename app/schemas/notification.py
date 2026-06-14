from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from ..models import NotificationType


class NotificationResponse(BaseModel):
    id: int
    type: NotificationType
    title: str
    content: Optional[str] = None
    sender_id: Optional[int] = None
    recipient_id: int
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationMarkRead(BaseModel):
    notification_ids: list[int]
