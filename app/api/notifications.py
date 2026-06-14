from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import User, Notification
from ..schemas.notification import NotificationResponse, NotificationMarkRead
from ..utils.security import get_current_user, require_roles
from ..services.notification_service_crud import (
    get_user_notifications, mark_notifications_read, mark_all_read,
)
from ..services.notification_service import notification_manager

router = APIRouter(prefix="/notifications", tags=["通知与消息推送"])


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_notifications(db, current_user.id, skip, limit, unread_only)


@router.post("/read")
def read_notifications(
    data: NotificationMarkRead,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = mark_notifications_read(db, current_user.id, data.notification_ids)
    return {"status": "success", "marked_count": count}


@router.post("/read-all")
def read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = mark_all_read(db, current_user.id)
    return {"status": "success", "marked_count": count}


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(Notification.recipient_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return {"unread_count": count}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db),
):
    from ..utils.security import SECRET_KEY, ALGORITHM
    from jose import JWTError, jwt
    from ..config import settings

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = int(payload.get("sub"))
    except (JWTError, Exception):
        await websocket.close(code=1008, reason="认证失败")
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        await websocket.close(code=1008, reason="用户不存在")
        return
    if not user.is_active:
        await websocket.close(code=1008, reason="用户已禁用")
        return

    enterprise_id = user.enterprise_id

    await notification_manager.connect(websocket, user_id, enterprise_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, user_id, enterprise_id)
