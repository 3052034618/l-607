from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from ..database import get_db
from ..models import (
    TransportPlan, PlanStatus, TransportPermit, PermitStatus,
    ConstructionSite, DisposalSite, User, Vehicle,
)
from ..schemas.permit import (
    TransportPlanCreate, TransportPlanApprove, TransportPlanReject,
    TransportPlanUpdate, TransportPlanResponse,
    TransportPermitIssue, TransportPermitRevoke, TransportPermitResponse,
)
from ..utils.security import get_current_user, require_roles
from ..utils.id_generator import generate_permit_number
from ..services.scheduling_service import recommend_disposal_sites
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType

router = APIRouter(prefix="/transport", tags=["渣土外运计划与电子准运证"])


@router.post("/plans", response_model=TransportPlanResponse)
async def create_transport_plan(
    plan_in: TransportPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "construction_unit", "transport_company", "city_management"
    )),
):
    cs = db.query(ConstructionSite).filter(
        ConstructionSite.id == plan_in.construction_site_id
    ).first()
    if not cs:
        raise HTTPException(status_code=404, detail="工地不存在")

    plan_code = f"TP{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
    plan = TransportPlan(
        plan_code=plan_code,
        construction_site_id=plan_in.construction_site_id,
        transport_company_id=plan_in.transport_company_id,
        waste_type=plan_in.waste_type,
        planned_volume=plan_in.planned_volume,
        planned_trips=plan_in.planned_trips,
        planned_date=plan_in.planned_date,
        start_time=plan_in.start_time,
        end_time=plan_in.end_time,
        status=PlanStatus.PENDING,
        created_by=current_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans", response_model=List[TransportPlanResponse])
def list_transport_plans(
    status: Optional[PlanStatus] = None,
    construction_site_id: Optional[int] = None,
    transport_company_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TransportPlan)
    if status:
        query = query.filter(TransportPlan.status == status)
    if construction_site_id:
        query = query.filter(TransportPlan.construction_site_id == construction_site_id)
    if transport_company_id:
        query = query.filter(TransportPlan.transport_company_id == transport_company_id)
    elif current_user.role == "transport_company" and current_user.enterprise_id:
        query = query.filter(TransportPlan.transport_company_id == current_user.enterprise_id)
    if start_date:
        query = query.filter(TransportPlan.planned_date >= start_date)
    if end_date:
        query = query.filter(TransportPlan.planned_date <= end_date)
    return query.order_by(TransportPlan.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/plans/{plan_id}", response_model=TransportPlanResponse)
def get_transport_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.query(TransportPlan).filter(TransportPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="运输计划不存在")
    return plan


@router.put("/plans/{plan_id}", response_model=TransportPlanResponse)
def update_transport_plan(
    plan_id: int,
    plan_in: TransportPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "construction_unit"
    )),
):
    plan = db.query(TransportPlan).filter(TransportPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="运输计划不存在")
    update_data = plan_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/plans/{plan_id}/approve", response_model=TransportPlanResponse)
async def approve_transport_plan(
    plan_id: int,
    approval: TransportPlanApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    plan = db.query(TransportPlan).filter(TransportPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="运输计划不存在")
    if plan.status != PlanStatus.PENDING:
        raise HTTPException(status_code=400, detail="只有待审批状态可以批准")

    ds = db.query(DisposalSite).filter(DisposalSite.id == approval.disposal_site_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="消纳场不存在")

    plan.disposal_site_id = approval.disposal_site_id
    plan.recommended_route = approval.recommended_route or []
    plan.status = PlanStatus.APPROVED
    plan.approved_by = current_user.id
    plan.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    await send_notification(
        db,
        NotificationType.PLAN_APPROVED,
        "运输计划已批准",
        f"您的运输计划{plan.plan_code}已批准，推荐消纳场：{ds.name}",
        enterprise_id=plan.transport_company_id,
        related_type="transport_plan",
        related_id=plan.id,
    )
    return plan


@router.post("/plans/{plan_id}/reject", response_model=TransportPlanResponse)
async def reject_transport_plan(
    plan_id: int,
    rejection: TransportPlanReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    plan = db.query(TransportPlan).filter(TransportPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="运输计划不存在")
    plan.status = PlanStatus.REJECTED
    plan.rejection_reason = rejection.rejection_reason
    db.commit()
    db.refresh(plan)

    await send_notification(
        db,
        NotificationType.PLAN_REJECTED,
        "运输计划已拒绝",
        f"您的运输计划{plan.plan_code}已被拒绝，原因：{rejection.rejection_reason}",
        enterprise_id=plan.transport_company_id,
        related_type="transport_plan",
        related_id=plan.id,
    )
    return plan


@router.post("/permits", response_model=TransportPermitResponse)
async def issue_permit(
    permit_in: TransportPermitIssue,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "transport_company"
    )),
):
    plan = db.query(TransportPlan).filter(TransportPlan.id == permit_in.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="运输计划不存在")
    if plan.status not in [PlanStatus.APPROVED, PlanStatus.IN_PROGRESS]:
        raise HTTPException(status_code=400, detail="运输计划状态不允许签发准运证")

    vehicle = db.query(Vehicle).filter(Vehicle.id == permit_in.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    cs = db.query(ConstructionSite).filter(
        ConstructionSite.id == permit_in.construction_site_id
    ).first()
    permit_number = generate_permit_number(cs.site_code if cs else "SITE")
    qr_data = f"PERMIT:{permit_number}:{permit_in.valid_from.isoformat()}:{permit_in.valid_to.isoformat()}"

    permit = TransportPermit(
        permit_number=permit_number,
        plan_id=permit_in.plan_id,
        vehicle_id=permit_in.vehicle_id,
        construction_site_id=permit_in.construction_site_id,
        disposal_site_id=permit_in.disposal_site_id,
        planned_route=permit_in.planned_route or [],
        valid_from=permit_in.valid_from,
        valid_to=permit_in.valid_to,
        max_volume=permit_in.max_volume,
        qr_code_data=qr_data,
        status=PermitStatus.ISSUED,
    )
    db.add(permit)
    db.commit()
    db.refresh(permit)

    if plan.status == PlanStatus.APPROVED:
        plan.status = PlanStatus.IN_PROGRESS
        db.commit()

    await send_notification(
        db,
        NotificationType.PERMIT_ISSUED,
        "电子准运证已签发",
        f"准运证号：{permit_number}，车辆：{vehicle.plate_number}，有效期至：{permit_in.valid_to}",
        enterprise_id=plan.transport_company_id,
        related_type="permit",
        related_id=permit.id,
    )
    return permit


@router.get("/permits", response_model=List[TransportPermitResponse])
def list_permits(
    status: Optional[PermitStatus] = None,
    vehicle_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TransportPermit)
    if status:
        query = query.filter(TransportPermit.status == status)
    if vehicle_id:
        query = query.filter(TransportPermit.vehicle_id == vehicle_id)
    if plan_id:
        query = query.filter(TransportPermit.plan_id == plan_id)
    return query.order_by(TransportPermit.issued_at.desc()).offset(skip).limit(limit).all()


@router.get("/permits/{permit_id}", response_model=TransportPermitResponse)
def get_permit(
    permit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permit = db.query(TransportPermit).filter(TransportPermit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="准运证不存在")
    return permit


@router.get("/permits/by-number/{permit_number}", response_model=TransportPermitResponse)
def get_permit_by_number(
    permit_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permit = db.query(TransportPermit).filter(
        TransportPermit.permit_number == permit_number
    ).first()
    if not permit:
        raise HTTPException(status_code=404, detail="准运证不存在")
    return permit


@router.post("/permits/{permit_id}/activate", response_model=TransportPermitResponse)
def activate_permit(
    permit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "transport_company", "site_manager"
    )),
):
    permit = db.query(TransportPermit).filter(TransportPermit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="准运证不存在")
    if permit.status != PermitStatus.ISSUED:
        raise HTTPException(status_code=400, detail="只有已签发状态可以激活")
    now = datetime.utcnow()
    if now < permit.valid_from or now > permit.valid_to:
        raise HTTPException(status_code=400, detail="准运证不在有效期内")
    permit.status = PermitStatus.ACTIVE
    db.commit()
    db.refresh(permit)
    return permit


@router.post("/permits/{permit_id}/revoke", response_model=TransportPermitResponse)
def revoke_permit(
    permit_id: int,
    revoke: TransportPermitRevoke,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    permit = db.query(TransportPermit).filter(TransportPermit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="准运证不存在")
    if permit.status in [PermitStatus.USED, PermitStatus.EXPIRED, PermitStatus.REVOKED]:
        raise HTTPException(status_code=400, detail="该准运证无法撤销")
    permit.status = PermitStatus.REVOKED
    permit.revoked_reason = revoke.revoked_reason
    db.commit()
    db.refresh(permit)
    return permit
