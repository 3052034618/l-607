from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class WeighingRecord(Base):
    __tablename__ = "weighing_records"

    id = Column(Integer, primary_key=True, index=True)
    record_code = Column(String(50), unique=True, index=True)
    permit_id = Column(Integer, ForeignKey("transport_permits.id"))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    construction_site_id = Column(Integer, ForeignKey("construction_sites.id"), nullable=False)
    disposal_site_id = Column(Integer, ForeignKey("disposal_sites.id"), nullable=False)
    gross_weight = Column(Float)
    tare_weight = Column(Float)
    net_weight = Column(Float)
    volume = Column(Float)
    entry_weight_time = Column(DateTime, default=datetime.utcnow)
    exit_weight_time = Column(DateTime)
    disposal_entry_time = Column(DateTime)
    disposal_unload_time = Column(DateTime)
    entry_images = Column(JSON, default=list)
    exit_images = Column(JSON, default=list)
    is_overloaded = Column(Boolean, default=False)
    overload_percentage = Column(Float, default=0)
    is_sealed = Column(Boolean, default=True)
    status = Column(String(20), default="in_transit")

    permit = relationship("TransportPermit", back_populates="weighing_record")
    vehicle = relationship("Vehicle", back_populates="weighing_records")
    construction_site = relationship("ConstructionSite", back_populates="weighing_records")
    disposal_site = relationship("DisposalSite", back_populates="weighing_records")
    violations = relationship("Violation", back_populates="weighing_record")


class TrackRecord(Base):
    __tablename__ = "track_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    permit_id = Column(Integer, ForeignKey("transport_permits.id"))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float)
    heading = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_off_route = Column(Boolean, default=False)
    off_route_distance = Column(Float, default=0)
    gps_signal = Column(Float)

    vehicle = relationship("Vehicle", back_populates="track_records")
