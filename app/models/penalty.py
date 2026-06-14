from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class PenaltyStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    PAID = "paid"
    APPEALED = "appealed"


class Penalty(Base):
    __tablename__ = "penalties"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), unique=True, index=True, nullable=False)
    violation_id = Column(Integer, ForeignKey("violations.id"))
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    violation_type = Column(String(100))
    description = Column(Text)
    fine_amount = Column(Float, nullable=False)
    credit_deduction = Column(Float, default=0)
    status = Column(Enum(PenaltyStatus), default=PenaltyStatus.DRAFT)
    submitter_id = Column(Integer, ForeignKey("users.id"))
    submitted_at = Column(DateTime)
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    approval_remark = Column(Text)
    rejection_reason = Column(Text)
    published_at = Column(DateTime)
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="penalties")
    vehicle = relationship("Vehicle", back_populates="penalties")
    approver = relationship("User", foreign_keys=[approver_id], back_populates="handled_penalties")


class CreditRecord(Base):
    __tablename__ = "credit_records"

    id = Column(Integer, primary_key=True, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    score_before = Column(Float, nullable=False)
    score_change = Column(Float, nullable=False)
    score_after = Column(Float, nullable=False)
    reason = Column(String(500))
    related_type = Column(String(50))
    related_id = Column(Integer)
    operator_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="credit_records")
