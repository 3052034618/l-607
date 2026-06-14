from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from ..models import ViolationType, ViolationLevel, WorkOrderStatus, PenaltyStatus, SettlementStatus


class ViolationResponse(BaseModel):
    id: int
    violation_code: Optional[str] = None
    type: ViolationType
    level: ViolationLevel
    description: Optional[str] = None
    vehicle_id: Optional[int] = None
    permit_id: Optional[int] = None
    weighing_record_id: Optional[int] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    detected_at: datetime
    is_auto_detected: bool
    model_config = ConfigDict(from_attributes=True)


class WorkOrderAssign(BaseModel):
    team_id: int
    assignee_id: Optional[int] = None


class WorkOrderComplete(BaseModel):
    result: str
    penalty_suggested: bool = False
    credit_deduction: float = 0.0


class WorkOrderResponse(BaseModel):
    id: int
    order_number: str
    violation_id: int
    team_id: Optional[int] = None
    assignee_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: ViolationLevel
    status: WorkOrderStatus
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    penalty_suggested: bool
    credit_deduction: float
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PenaltyCreate(BaseModel):
    violation_id: Optional[int] = None
    enterprise_id: int
    vehicle_id: Optional[int] = None
    violation_type: str
    description: Optional[str] = None
    fine_amount: float
    credit_deduction: float = 0.0


class PenaltyApprove(BaseModel):
    approval_remark: Optional[str] = None


class PenaltyReject(BaseModel):
    rejection_reason: str


class PenaltyResponse(BaseModel):
    id: int
    ticket_number: str
    violation_id: Optional[int] = None
    enterprise_id: int
    vehicle_id: Optional[int] = None
    violation_type: str
    description: Optional[str] = None
    fine_amount: float
    credit_deduction: float
    status: PenaltyStatus
    approver_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CreditRecordResponse(BaseModel):
    id: int
    enterprise_id: int
    score_before: float
    score_change: float
    score_after: float
    reason: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SettlementGenerate(BaseModel):
    enterprise_id: int
    construction_site_id: int
    period_start: datetime
    period_end: datetime


class SettlementConfirm(BaseModel):
    pass


class SettlementResponse(BaseModel):
    id: int
    settlement_number: str
    enterprise_id: int
    construction_site_id: int
    period_start: datetime
    period_end: datetime
    total_trips: int
    total_volume: float
    total_distance: float
    transport_cost: float
    disposal_cost: float
    penalty_deduction: float
    total_amount: float
    status: SettlementStatus
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DailyReportResponse(BaseModel):
    id: int
    report_id: str
    report_date: datetime
    total_transports: int
    total_volume: float
    total_accepted_volume: float
    total_violations: int
    avg_transport_duration: float
    site_stats: List
    disposal_stats: List
    district_stats: List
    violation_stats: dict
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)
