from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import (
    Violation, WorkOrder, WorkOrderStatus, ViolationType, ViolationLevel,
    EnforcementTeam, User, CreditRecord, Enterprise,
)
from ..schemas.business import (
    ViolationResponse, WorkOrderAssign, WorkOrderComplete, WorkOrderResponse,
    CreditRecordResponse,
)
from ..utils.security import get_current_user, require_roles
from ..services.violation_service import (
    assign_work_order, auto_assign_work_order, complete_work_order, create_violation,
)
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType

router = APIRouter(prefix="/enforcement", tags=["违规告警与执法工单"])


@router.get("/violations", response_model=List[ViolationResponse])
def list_violations(
    type: Optional[ViolationType] = None,
    level: Optional[ViolationLevel] = None,
    vehicle_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Violation)
    if type:
        query = query.filter(Violation.type == type)
    if level:
        query = query.filter(Violation.level == level)
    if vehicle_id:
        query = query.filter(Violation.vehicle_id == vehicle_id)
    if start_date:
        query = query.filter(Violation.detected_at >= start_date)
    if end_date:
        query = query.filter(Violation.detected_at <= end_date)
    return query.order_by(Violation.detected_at.desc()).offset(skip).limit(limit).all()


@router.get("/violations/{violation_id}", response_model=ViolationResponse)
def get_violation(
    violation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    v = db.query(Violation).filter(Violation.id == violation_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="违规记录不存在")
    return v


@router.post("/violations/manual", response_model=ViolationResponse)
def create_manual_violation(
    violation_type: ViolationType,
    description: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    location_lat: Optional[float] = None,
    location_lng: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management", "enforcement_team")),
):
    return create_violation(
        db,
        violation_type=violation_type,
        description=description,
        vehicle_id=vehicle_id,
        location_lat=location_lat,
        location_lng=location_lng,
        is_auto_detected=False,
    )


@router.get("/work-orders", response_model=List[WorkOrderResponse])
def list_work_orders(
    status: Optional[WorkOrderStatus] = None,
    priority: Optional[ViolationLevel] = None,
    team_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(WorkOrder)
    if status:
        query = query.filter(WorkOrder.status == status)
    if priority:
        query = query.filter(WorkOrder.priority == priority)
    if team_id:
        query = query.filter(WorkOrder.team_id == team_id)
    elif current_user.role == "enforcement_team" and current_user.enforcement_team_id:
        query = query.filter(WorkOrder.team_id == current_user.enforcement_team_id)
    if assignee_id:
        query = query.filter(WorkOrder.assignee_id == assignee_id)
    return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/work-orders/{order_id}", response_model=WorkOrderResponse)
def get_work_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    o = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="工单不存在")
    return o


@router.post("/work-orders/{order_id}/assign", response_model=WorkOrderResponse)
async def assign_order(
    order_id: int,
    assign: WorkOrderAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        order = assign_work_order(db, order_id, assign.team_id, assign.assignee_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if assign.team_id:
        team = db.query(EnforcementTeam).filter(EnforcementTeam.id == assign.team_id).first()
        if team:
            await send_notification(
                db,
                NotificationType.WORK_ORDER_ASSIGNED,
                "新工单已分配",
                f"执法队{team.name}收到新工单：{order.title}，优先级：{order.priority.value}",
                related_type="work_order",
                related_id=order.id,
            )
    return order


@router.post("/work-orders/{order_id}/auto-assign", response_model=WorkOrderResponse)
def auto_assign_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status != WorkOrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="只有待分配工单可自动分配")
    return auto_assign_work_order(db, order)


@router.post("/work-orders/{order_id}/start")
def start_work_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("enforcement_team", "admin")),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status not in [WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS]:
        raise HTTPException(status_code=400, detail="只有已分配工单可开始处理")
    if not order.assignee_id:
        order.assignee_id = current_user.id
    order.status = WorkOrderStatus.IN_PROGRESS
    db.commit()
    db.refresh(order)
    return {"status": "success", "work_order_id": order_id, "new_status": order.status.value}


@router.post("/work-orders/{order_id}/complete", response_model=WorkOrderResponse)
async def complete_order(
    order_id: int,
    complete: WorkOrderComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("enforcement_team", "admin")),
):
    try:
        order = await complete_work_order(
            db, order_id, complete.result, complete.penalty_suggested,
            complete.credit_deduction, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await send_notification(
        db,
        NotificationType.WORK_ORDER_COMPLETED,
        "工单已完成",
        f"工单{order.order_number}已完成处置，结果：{complete.result[:50]}",
        related_type="work_order",
        related_id=order.id,
    )
    return order


@router.post("/work-orders/{order_id}/close")
def close_work_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.status != WorkOrderStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="只有已完成工单可关闭")
    order.status = WorkOrderStatus.CLOSED
    db.commit()
    db.refresh(order)
    return {"status": "success", "work_order_id": order_id, "new_status": order.status.value}


@router.get("/enterprises/{ent_id}/credit-records", response_model=List[CreditRecordResponse])
def get_enterprise_credit_records(
    ent_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ent = db.query(Enterprise).filter(Enterprise.id == ent_id).first()
    if not ent:
        raise HTTPException(status_code=404, detail="企业不存在")
    records = (
        db.query(CreditRecord)
        .filter(CreditRecord.enterprise_id == ent_id)
        .order_by(CreditRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return records
