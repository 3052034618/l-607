from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import (
    Penalty, PenaltyStatus, Violation, User, Enterprise,
)
from ..schemas.business import (
    PenaltyCreate, PenaltyApprove, PenaltyReject, PenaltyResponse,
)
from ..utils.security import get_current_user, require_roles
from ..services.penalty_service import (
    create_penalty, suggest_penalty_from_violation, submit_penalty_for_approval,
    approve_penalty, reject_penalty, publish_penalty, mark_penalty_paid,
)
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType

router = APIRouter(prefix="/penalties", tags=["处罚管理"])


@router.get("", response_model=List[PenaltyResponse])
def list_penalties(
    status: Optional[PenaltyStatus] = None,
    enterprise_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    violation_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Penalty)
    if status:
        query = query.filter(Penalty.status == status)
    if enterprise_id:
        query = query.filter(Penalty.enterprise_id == enterprise_id)
    elif current_user.enterprise_id and current_user.role in [
        "construction_unit", "transport_company",
    ]:
        query = query.filter(Penalty.enterprise_id == current_user.enterprise_id)
    if vehicle_id:
        query = query.filter(Penalty.vehicle_id == vehicle_id)
    if violation_type:
        query = query.filter(Penalty.violation_type == violation_type)
    return query.order_by(Penalty.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{penalty_id}", response_model=PenaltyResponse)
def get_penalty(
    penalty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="处罚单不存在")
    return p


@router.post("", response_model=PenaltyResponse)
def create_new_penalty(
    penalty_in: PenaltyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "enforcement_team"
    )),
):
    return create_penalty(
        db,
        enterprise_id=penalty_in.enterprise_id,
        vehicle_id=penalty_in.vehicle_id,
        violation_type=penalty_in.violation_type,
        description=penalty_in.description,
        fine_amount=penalty_in.fine_amount,
        credit_deduction=penalty_in.credit_deduction,
        violation_id=penalty_in.violation_id,
        submitter_id=current_user.id,
    )


@router.post("/suggest/from-violation/{violation_id}", response_model=PenaltyResponse)
def suggest_from_violation(
    violation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "enforcement_team"
    )),
):
    p = suggest_penalty_from_violation(db, violation_id)
    if not p:
        raise HTTPException(status_code=404, detail="无法根据违规生成处罚建议")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/{penalty_id}/submit", response_model=PenaltyResponse)
async def submit_for_approval(
    penalty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "enforcement_team"
    )),
):
    try:
        p = submit_penalty_for_approval(db, penalty_id, current_user.id)
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))

    await send_notification(
        db,
        NotificationType.PENALTY_PENDING,
        "处罚单待审批",
        f"有新的处罚单待审批：{p.ticket_number}，罚款金额：{p.fine_amount}元",
        related_type="penalty",
        related_id=p.id,
    )
    return p


@router.post("/{penalty_id}/approve", response_model=PenaltyResponse)
async def approve(
    penalty_id: int,
    approval: Optional[PenaltyApprove] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        p = await approve_penalty(
            db, penalty_id, current_user.id,
            approval.approval_remark if approval else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return p


@router.post("/{penalty_id}/reject", response_model=PenaltyResponse)
def reject(
    penalty_id: int,
    rejection: PenaltyReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        return reject_penalty(db, penalty_id, current_user.id, rejection.rejection_reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{penalty_id}/publish", response_model=PenaltyResponse)
async def publish(
    penalty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        return await publish_penalty(db, penalty_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{penalty_id}/mark-paid", response_model=PenaltyResponse)
def mark_paid(
    penalty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        return mark_penalty_paid(db, penalty_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
