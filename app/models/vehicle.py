from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class VehicleStatus(str, enum.Enum):
    IDLE = "idle"
    LOADING = "loading"
    TRANSPORTING = "transporting"
    UNLOADING = "unloading"
    MAINTENANCE = "maintenance"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), unique=True, index=True, nullable=False)
    vehicle_type = Column(String(50))
    load_capacity = Column(Float, nullable=False)
    container_volume = Column(Float, nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False)
    driver_name = Column(String(50))
    driver_phone = Column(String(20))
    gps_device_id = Column(String(100))
    has_sealing_device = Column(Boolean, default=True)
    status = Column(Enum(VehicleStatus), default=VehicleStatus.IDLE)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="vehicles")
    permits = relationship("TransportPermit", back_populates="vehicle")
    weighing_records = relationship("WeighingRecord", back_populates="vehicle")
    track_records = relationship("TrackRecord", back_populates="vehicle")
    penalties = relationship("Penalty", back_populates="vehicle")


class CapacityRecord(Base):
    __tablename__ = "capacity_records"

    id = Column(Integer, primary_key=True, index=True)
    disposal_site_id = Column(Integer, ForeignKey("disposal_sites.id"), nullable=False)
    remaining_capacity = Column(Float, nullable=False)
    daily_accepted = Column(Float, default=0)
    reported_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String(50))

    disposal_site = relationship("DisposalSite", back_populates="capacity_records")
