from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import ConstructionSite, DisposalSite, User
from ..schemas.site import (
    ConstructionSiteCreate, ConstructionSiteUpdate, ConstructionSiteResponse,
    DisposalSiteCreate, DisposalSiteUpdate, DisposalSiteResponse,
    DisposalSiteCapacityReport, CapacityRecordResponse, DisposalSiteRecommendation,
)
from ..utils.security import get_current_user, require_roles
from ..services.scheduling_service import (
    recommend_disposal_sites, report_disposal_capacity, balance_transport_allocation,
)
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType

router = APIRouter(prefix="/sites", tags=["工地与消纳场管理"])


@router.post("/construction", response_model=ConstructionSiteResponse)
def create_construction_site(
    site_in: ConstructionSiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "construction_unit", "city_management")),
):
    if current_user.role == "construction_unit" and current_user.enterprise_id:
        site_in.enterprise_id = current_user.enterprise_id
    site = ConstructionSite(**site_in.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/construction", response_model=List[ConstructionSiteResponse])
def list_construction_sites(
    district: Optional[str] = None,
    enterprise_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ConstructionSite).filter(ConstructionSite.is_active == True)
    if district:
        query = query.filter(ConstructionSite.district == district)
    if enterprise_id:
        query = query.filter(ConstructionSite.enterprise_id == enterprise_id)
    elif current_user.role == "construction_unit" and current_user.enterprise_id:
        query = query.filter(ConstructionSite.enterprise_id == current_user.enterprise_id)
    return query.offset(skip).limit(limit).all()


@router.get("/construction/{site_id}", response_model=ConstructionSiteResponse)
def get_construction_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = db.query(ConstructionSite).filter(ConstructionSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="工地不存在")
    return site


@router.put("/construction/{site_id}", response_model=ConstructionSiteResponse)
def update_construction_site(
    site_id: int,
    site_in: ConstructionSiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "construction_unit", "city_management")),
):
    site = db.query(ConstructionSite).filter(ConstructionSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="工地不存在")
    if current_user.role == "construction_unit" and current_user.enterprise_id:
        if site.enterprise_id != current_user.enterprise_id:
            raise HTTPException(status_code=403, detail="无权修改此工地")
    update_data = site_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.post("/disposal", response_model=DisposalSiteResponse)
def create_disposal_site(
    site_in: DisposalSiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    site = DisposalSite(**site_in.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.get("/disposal", response_model=List[DisposalSiteResponse])
def list_disposal_sites(
    district: Optional[str] = None,
    has_capacity: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DisposalSite).filter(DisposalSite.is_active == True)
    if district:
        query = query.filter(DisposalSite.district == district)
    if has_capacity:
        query = query.filter(DisposalSite.remaining_capacity > 0)
    if current_user.role == "disposal" and current_user.enterprise_id:
        query = query.filter(DisposalSite.enterprise_id == current_user.enterprise_id)
    return query.offset(skip).limit(limit).all()


@router.get("/disposal/{site_id}", response_model=DisposalSiteResponse)
def get_disposal_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    site = db.query(DisposalSite).filter(DisposalSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="消纳场不存在")
    return site


@router.put("/disposal/{site_id}", response_model=DisposalSiteResponse)
def update_disposal_site(
    site_id: int,
    site_in: DisposalSiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    site = db.query(DisposalSite).filter(DisposalSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="消纳场不存在")
    update_data = site_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site


@router.post("/disposal/{site_id}/report-capacity", response_model=CapacityRecordResponse)
async def report_capacity(
    site_id: int,
    report: DisposalSiteCapacityReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management", "disposal")),
):
    site = db.query(DisposalSite).filter(DisposalSite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="消纳场不存在")

    if current_user.role == "disposal" and current_user.enterprise_id:
        if site.enterprise_id != current_user.enterprise_id:
            raise HTTPException(status_code=403, detail="无权上报此消纳场容量")

    try:
        record = report_disposal_capacity(
            db, site_id, report.remaining_capacity, report.daily_accepted, report.source
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    site = db.query(DisposalSite).filter(DisposalSite.id == site_id).first()
    if site and site.remaining_capacity < site.total_capacity * 0.1:
        await send_notification(
            db,
            NotificationType.CAPACITY_ALERT,
            "消纳场容量告警",
            f"消纳场{site.name}剩余容量不足10%，请及时调整运输计划",
            related_type="disposal_site",
            related_id=site_id,
            enterprise_id=site.enterprise_id,
        )
    return record


@router.get("/disposal/{site_id}/capacity-history", response_model=List[CapacityRecordResponse])
def get_capacity_history(
    site_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from ..models.vehicle import CapacityRecord
    query = db.query(CapacityRecord).filter(CapacityRecord.disposal_site_id == site_id)
    if start_date:
        query = query.filter(CapacityRecord.reported_at >= start_date)
    if end_date:
        query = query.filter(CapacityRecord.reported_at <= end_date)
    return query.order_by(CapacityRecord.reported_at.desc()).offset(skip).limit(limit).all()


@router.get("/recommend/disposal", response_model=List[DisposalSiteRecommendation])
def get_recommendations(
    construction_site_id: int = Query(..., description="工地ID"),
    planned_volume: float = Query(..., description="计划出土量(立方米)", gt=0),
    planned_date: datetime = Query(..., description="计划日期"),
    waste_type: Optional[str] = Query(None, description="渣土类型"),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "construction_unit", "transport_company"
    )),
):
    recs = recommend_disposal_sites(
        db, construction_site_id, planned_volume, planned_date, waste_type, top_k
    )
    if not recs:
        raise HTTPException(status_code=404, detail="未找到合适的消纳场")
    return recs


@router.post("/balance-allocation")
def get_balanced_allocation(
    construction_site_id: int = Query(..., description="工地ID"),
    requested_volume: float = Query(..., description="请求出土量(立方米)", gt=0),
    planned_date: datetime = Query(..., description="计划日期"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    allocations = balance_transport_allocation(
        db, construction_site_id, requested_volume, planned_date
    )
    return {
        "construction_site_id": construction_site_id,
        "requested_volume": requested_volume,
        "planned_date": planned_date,
        "allocations": allocations,
    }
