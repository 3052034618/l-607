from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CONSTRUCTION_UNIT = "construction_unit"
    TRANSPORT_COMPANY = "transport_company"
    CITY_MANAGEMENT = "city_management"
    ENFORCEMENT_TEAM = "enforcement_team"
    SITE_MANAGER = "site_manager"


class EnterpriseType(str, enum.Enum):
    CONSTRUCTION = "construction"
    TRANSPORT = "transport"
    DISPOSAL = "disposal"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    role = Column(Enum(UserRole), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"))
    enforcement_team_id = Column(Integer, ForeignKey("enforcement_teams.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enterprise = relationship("Enterprise", back_populates="users")
    enforcement_team = relationship("EnforcementTeam", back_populates="members")
    created_notifications = relationship("Notification", foreign_keys="Notification.sender_id", back_populates="sender")
    received_notifications = relationship("Notification", foreign_keys="Notification.recipient_id", back_populates="recipient")
    assigned_work_orders = relationship("WorkOrder", foreign_keys="WorkOrder.assignee_id", back_populates="assignee")
    handled_penalties = relationship("Penalty", foreign_keys="Penalty.approver_id", back_populates="approver")


class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    type = Column(Enum(EnterpriseType), nullable=False)
    unified_social_credit_code = Column(String(50), unique=True)
    legal_person = Column(String(50))
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    address = Column(String(500))
    credit_score = Column(Float, default=100.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="enterprise")
    construction_sites = relationship("ConstructionSite", back_populates="enterprise")
    vehicles = relationship("Vehicle", back_populates="enterprise")
    transport_plans = relationship("TransportPlan", back_populates="transport_company")
    settlements = relationship("Settlement", back_populates="enterprise")
    credit_records = relationship("CreditRecord", back_populates="enterprise")
    penalties = relationship("Penalty", back_populates="enterprise")


class EnforcementTeam(Base):
    __tablename__ = "enforcement_teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    team_code = Column(String(50), unique=True)
    region = Column(String(100))
    team_leader = Column(String(50))
    contact_phone = Column(String(20))
    workload_weight = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", back_populates="enforcement_team")
    work_orders = relationship("WorkOrder", back_populates="team")
