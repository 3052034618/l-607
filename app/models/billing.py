from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class SettlementStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    BILLED = "billed"
    PAID = "paid"
    DISPUTED = "disputed"


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    settlement_number = Column(String(50), unique=True, index=True, nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    construction_site_id = Column(Integer, ForeignKey("construction_sites.id"), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_trips = Column(Integer, default=0)
    total_volume = Column(Float, default=0)
    total_distance = Column(Float, default=0)
    transport_cost = Column(Float, default=0)
    disposal_cost = Column(Float, default=0)
    penalty_deduction = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    status = Column(Enum(SettlementStatus), default=SettlementStatus.DRAFT)
    detail_summary = Column(JSON, default=dict)
    confirmed_by = Column(Integer, ForeignKey("users.id"))
    confirmed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="settlements")
    construction_site = relationship("ConstructionSite", back_populates="settlements")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(50), unique=True, index=True, nullable=False)
    report_date = Column(DateTime, unique=True, nullable=False)
    total_transports = Column(Integer, default=0)
    total_volume = Column(Float, default=0)
    total_accepted_volume = Column(Float, default=0)
    total_violations = Column(Integer, default=0)
    avg_transport_duration = Column(Float, default=0)
    site_stats = Column(JSON, default=list)
    disposal_stats = Column(JSON, default=list)
    district_stats = Column(JSON, default=list)
    violation_stats = Column(JSON, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)
