from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import Notification, NotificationType, User, Enterprise
from .notification_service import notification_manager


def create_notification(
    db: Session,
    type: NotificationType,
    title: str,
    content: Optional[str] = None,
    sender_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> Notification:
    notification = Notification(
        type=type,
        title=title,
        content=content,
        sender_id=sender_id,
        recipient_id=recipient_id,
        enterprise_id=enterprise_id,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


async def send_notification(
    db: Session,
    type: NotificationType,
    title: str,
    content: Optional[str] = None,
    sender_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> Notification:
    notification = create_notification(
        db, type, title, content, sender_id, recipient_id, enterprise_id, related_type, related_id
    )
    if recipient_id:
        await notification_manager.push_to_user(db, recipient_id, notification)
    elif enterprise_id:
        await notification_manager.push_to_enterprise(db, enterprise_id, notification)
    return notification


def get_user_notifications(
    db: Session, user_id: int, skip: int = 0, limit: int = 50, unread_only: bool = False
) -> List[Notification]:
    query = db.query(Notification).filter(Notification.recipient_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()


def mark_notifications_read(db: Session, user_id: int, notification_ids: List[int]) -> int:
    count = (
        db.query(Notification)
        .filter(
            Notification.id.in_(notification_ids),
            Notification.recipient_id == user_id,
            Notification.is_read == False,
        )
        .update(
            {Notification.is_read: True, Notification.read_at: datetime.utcnow()},
            synchronize_session=False,
        )
    )
    db.commit()
    return count


def mark_all_read(db: Session, user_id: int) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.recipient_id == user_id, Notification.is_read == False)
        .update(
            {Notification.is_read: True, Notification.read_at: datetime.utcnow()},
            synchronize_session=False,
        )
    )
    db.commit()
    return count
