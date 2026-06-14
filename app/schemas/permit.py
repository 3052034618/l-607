from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..models import PlanStatus, PermitStatus


class TransportPlanCreate(BaseModel):
    construction_site_id: int
    transport_company_id: int
    waste_type: Optional[str] = None
    planned_volume: float
    planned_trips: Optional[int] = None
    planned_date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TransportPlanApprove(BaseModel):
    disposal_site_id: int
    recommended_route: Optional[List[Dict[str, Any]]] = None


class TransportPlanReject(BaseModel):
    rejection_reason: str


class TransportPlanUpdate(BaseModel):
    status: Optional[PlanStatus] = None


class TransportPlanResponse(BaseModel):
    id: int
    plan_code: str
    construction_site_id: int
    transport_company_id: int
    disposal_site_id: Optional[int] = None
    waste_type: Optional[str] = None
    planned_volume: float
    planned_trips: Optional[int] = None
    planned_date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: PlanStatus
    rejection_reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TransportPermitIssue(BaseModel):
    plan_id: int
    vehicle_id: int
    construction_site_id: int
    disposal_site_id: int
    planned_route: Optional[List[Dict[str, Any]]] = None
    valid_from: datetime
    valid_to: datetime
    max_volume: Optional[float] = None


class TransportPermitRevoke(BaseModel):
    revoked_reason: str


class TransportPermitResponse(BaseModel):
    id: int
    permit_number: str
    plan_id: int
    vehicle_id: int
    construction_site_id: int
    disposal_site_id: int
    valid_from: datetime
    valid_to: datetime
    max_volume: Optional[float] = None
    status: PermitStatus
    issued_at: datetime
    used_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
