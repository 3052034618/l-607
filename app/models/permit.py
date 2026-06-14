from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

from ..database import Base


class PlanStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PermitStatus(str, enum.Enum):
    ISSUED = "issued"
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TransportPlan(Base):
    __tablename__ = "transport_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(50), unique=True, index=True, nullable=False)
    construction_site_id = Column(Integer, ForeignKey("construction_sites.id"), nullable=False)
    transport_company_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    disposal_site_id = Column(Integer, ForeignKey("disposal_sites.id"))
    waste_type = Column(String(50))
    planned_volume = Column(Float, nullable=False)
    planned_trips = Column(Integer)
    planned_date = Column(DateTime, nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    recommended_route = Column(JSON, default=list)
    status = Column(Enum(PlanStatus), default=PlanStatus.PENDING)
    rejection_reason = Column(String(500))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    construction_site = relationship("ConstructionSite", back_populates="transport_plans")
    transport_company = relationship("Enterprise", back_populates="transport_plans")
    permits = relationship("TransportPermit", back_populates="plan")


class TransportPermit(Base):
    __tablename__ = "transport_permits"

    id = Column(Integer, primary_key=True, index=True)
    permit_number = Column(String(50), unique=True, index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("transport_plans.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    construction_site_id = Column(Integer, ForeignKey("construction_sites.id"), nullable=False)
    disposal_site_id = Column(Integer, ForeignKey("disposal_sites.id"), nullable=False)
    planned_route = Column(JSON, default=list)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime, nullable=False)
    max_volume = Column(Float)
    qr_code_data = Column(String(500))
    status = Column(Enum(PermitStatus), default=PermitStatus.ISSUED)
    issued_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime)
    revoked_reason = Column(String(500))

    plan = relationship("TransportPlan", back_populates="permits")
    vehicle = relationship("Vehicle", back_populates="permits")
    weighing_record = relationship("WeighingRecord", uselist=False, back_populates="permit")
