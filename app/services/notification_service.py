from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import WebSocket

from ..models import Notification, NotificationType, User


class NotificationManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.enterprise_connections: Dict[int, List[WebSocket]] = {}

    async def startup(self):
        pass

    async def shutdown(self):
        for user_id, connections in list(self.active_connections.items()):
            for websocket in connections:
                await websocket.close()
        self.active_connections.clear()
        self.enterprise_connections.clear()

    async def connect(self, websocket: WebSocket, user_id: int, enterprise_id: Optional[int] = None):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        if enterprise_id:
            if enterprise_id not in self.enterprise_connections:
                self.enterprise_connections[enterprise_id] = []
            self.enterprise_connections[enterprise_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int, enterprise_id: Optional[int] = None):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        if enterprise_id and enterprise_id in self.enterprise_connections:
            if websocket in self.enterprise_connections[enterprise_id]:
                self.enterprise_connections[enterprise_id].remove(websocket)
            if not self.enterprise_connections[enterprise_id]:
                del self.enterprise_connections[enterprise_id]

    async def _send_to_websockets(self, websockets: List[WebSocket], message: Dict[str, Any]):
        for ws in list(websockets):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def push_to_user(self, db: Session, user_id: int, notification: Notification):
        message = {
            "type": "notification",
            "data": {
                "id": notification.id,
                "notification_type": notification.type.value,
                "title": notification.title,
                "content": notification.content,
                "related_type": notification.related_type,
                "related_id": notification.related_id,
                "created_at": notification.created_at.isoformat(),
            },
        }
        if user_id in self.active_connections:
            await self._send_to_websockets(self.active_connections[user_id], message)
            notification.is_pushed = True
            notification.pushed_at = datetime.utcnow()
            db.commit()

    async def push_to_enterprise(self, db: Session, enterprise_id: int, notification: Notification):
        message = {
            "type": "notification",
            "data": {
                "id": notification.id,
                "notification_type": notification.type.value,
                "title": notification.title,
                "content": notification.content,
                "related_type": notification.related_type,
                "related_id": notification.related_id,
                "created_at": notification.created_at.isoformat(),
            },
        }
        if enterprise_id in self.enterprise_connections:
            await self._send_to_websockets(self.enterprise_connections[enterprise_id], message)
        users = db.query(User).filter(User.enterprise_id == enterprise_id).all()
        for user in users:
            if user.id in self.active_connections:
                await self._send_to_websockets(self.active_connections[user.id], message)
        notification.is_pushed = True
        notification.pushed_at = datetime.utcnow()
        db.commit()

    async def push_status_update(self, user_id: int, entity_type: str, entity_id: int, status: str, extra: Dict = None):
        message = {
            "type": "status_update",
            "data": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status": status,
                "extra": extra or {},
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        if user_id in self.active_connections:
            await self._send_to_websockets(self.active_connections[user_id], message)


notification_manager = NotificationManager()
