from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class ViolationType(str, enum.Enum):
    OFF_ROUTE = "off_route"
    OVERTIME = "overtime"
    OVERLOAD = "overload"
    UNSEALED = "unsealed"
    NO_PERMIT = "no_permit"
    EXPIRED_PERMIT = "expired_permit"


class ViolationLevel(str, enum.Enum):
    MINOR = "minor"
    MEDIUM = "medium"
    MAJOR = "major"
    CRITICAL = "critical"


class WorkOrderStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    violation_code = Column(String(50), unique=True, index=True)
    type = Column(Enum(ViolationType), nullable=False)
    level = Column(Enum(ViolationLevel), nullable=False)
    description = Column(String(500))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))
    permit_id = Column(Integer, ForeignKey("transport_permits.id"))
    weighing_record_id = Column(Integer, ForeignKey("weighing_records.id"))
    location_lat = Column(Float)
    location_lng = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow)
    evidence_data = Column(Text)
    is_auto_detected = Column(Boolean, default=True)

    weighing_record = relationship("WeighingRecord", back_populates="violations")
    work_order = relationship("WorkOrder", uselist=False, back_populates="violation")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    violation_id = Column(Integer, ForeignKey("violations.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("enforcement_teams.id"))
    assignee_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))
    description = Column(Text)
    priority = Column(Enum(ViolationLevel), nullable=False)
    status = Column(Enum(WorkOrderStatus), default=WorkOrderStatus.PENDING)
    assigned_at = Column(DateTime)
    completed_at = Column(DateTime)
    result = Column(Text)
    penalty_suggested = Column(Boolean, default=False)
    credit_deduction = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    violation = relationship("Violation", back_populates="work_order")
    team = relationship("EnforcementTeam", back_populates="work_orders")
    assignee = relationship("User", back_populates="assigned_work_orders")
