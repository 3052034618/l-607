from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class NotificationType(str, enum.Enum):
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    PERMIT_ISSUED = "permit_issued"
    VIOLATION_ALERT = "violation_alert"
    WORK_ORDER_ASSIGNED = "work_order_assigned"
    WORK_ORDER_COMPLETED = "work_order_completed"
    PENALTY_PENDING = "penalty_pending"
    PENALTY_APPROVED = "penalty_approved"
    SETTLEMENT_READY = "settlement_ready"
    CAPACITY_ALERT = "capacity_alert"
    REPORT_READY = "report_ready"
    SYSTEM = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    sender_id = Column(Integer, ForeignKey("users.id"))
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enterprise_id = Column(Integer)
    related_type = Column(String(50))
    related_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    is_pushed = Column(Boolean, default=False)
    read_at = Column(DateTime)
    pushed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="created_notifications")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_notifications")
