from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class ConstructionSiteBase(BaseModel):
    site_code: str
    name: str
    enterprise_id: int
    address: Optional[str] = None
    district: Optional[str] = None
    latitude: float
    longitude: float
    project_manager: Optional[str] = None
    contact_phone: Optional[str] = None
    total_expected_volume: Optional[float] = None
    remaining_volume: Optional[float] = None
    daily_max_transports: int = 50
    allowed_transport_hours: Optional[Dict[str, Any]] = None


class ConstructionSiteCreate(ConstructionSiteBase):
    pass


class ConstructionSiteUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    project_manager: Optional[str] = None
    contact_phone: Optional[str] = None
    total_expected_volume: Optional[float] = None
    remaining_volume: Optional[float] = None
    daily_max_transports: Optional[int] = None
    allowed_transport_hours: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ConstructionSiteResponse(ConstructionSiteBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DisposalSiteBase(BaseModel):
    site_code: str
    name: str
    address: Optional[str] = None
    district: Optional[str] = None
    latitude: float
    longitude: float
    total_capacity: float
    remaining_capacity: float
    daily_acceptance_limit: Optional[float] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    acceptance_hours: Optional[Dict[str, Any]] = None
    restricted_types: Optional[List[str]] = None


class DisposalSiteCreate(DisposalSiteBase):
    pass


class DisposalSiteUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    total_capacity: Optional[float] = None
    remaining_capacity: Optional[float] = None
    daily_acceptance_limit: Optional[float] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    acceptance_hours: Optional[Dict[str, Any]] = None
    restricted_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DisposalSiteCapacityReport(BaseModel):
    remaining_capacity: float
    daily_accepted: Optional[float] = 0
    source: Optional[str] = "manual"


class DisposalSiteResponse(DisposalSiteBase):
    id: int
    daily_accepted: float
    is_active: bool
    last_update: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CapacityRecordResponse(BaseModel):
    id: int
    disposal_site_id: int
    remaining_capacity: float
    daily_accepted: float
    reported_at: datetime
    source: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class DisposalSiteRecommendation(BaseModel):
    disposal_site_id: int
    disposal_site_name: str
    distance_km: float
    remaining_capacity: float
    capacity_score: float
    distance_score: float
    time_score: float
    total_score: float
    estimated_cost: float
