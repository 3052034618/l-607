from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class ConstructionSite(Base):
    __tablename__ = "construction_sites"

    id = Column(Integer, primary_key=True, index=True)
    site_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    address = Column(String(500))
    district = Column(String(100))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    project_manager = Column(String(50))
    contact_phone = Column(String(20))
    total_expected_volume = Column(Float)
    remaining_volume = Column(Float)
    daily_max_transports = Column(Integer, default=50)
    allowed_transport_hours = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="construction_sites")
    transport_plans = relationship("TransportPlan", back_populates="construction_site")
    weighing_records = relationship("WeighingRecord", back_populates="construction_site")
    settlements = relationship("Settlement", back_populates="construction_site")


class DisposalSite(Base):
    __tablename__ = "disposal_sites"

    id = Column(Integer, primary_key=True, index=True)
    site_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    address = Column(String(500))
    district = Column(String(100))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    total_capacity = Column(Float, nullable=False)
    remaining_capacity = Column(Float, nullable=False)
    daily_acceptance_limit = Column(Float)
    daily_accepted = Column(Float, default=0)
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    acceptance_hours = Column(JSON, default=dict)
    restricted_types = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    last_update = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="disposal_sites")
    capacity_records = relationship("CapacityRecord", back_populates="disposal_site")
    weighing_records = relationship("WeighingRecord", back_populates="disposal_site")
