from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import (
    Vehicle, VehicleStatus, WeighingRecord, TrackRecord,
    TransportPermit, PermitStatus, User,
)
from ..schemas.vehicle import (
    VehicleCreate, VehicleUpdate, VehicleResponse,
    WeighingEntryCreate, WeighingExitUpdate, DisposalUnloadUpdate, WeighingRecordResponse,
    TrackPointCreate, TrackPointResponse,
)
from ..utils.security import get_current_user, require_roles
from ..services.violation_service import (
    check_overload, check_sealed, check_route_deviation, check_transport_timeout,
)
from ..services.scheduling_service import report_disposal_capacity
from ..models.site import DisposalSite

router = APIRouter(prefix="/vehicles", tags=["车辆管理与轨迹"])


@router.post("", response_model=VehicleResponse)
def create_vehicle(
    v_in: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "transport_company", "city_management"
    )),
):
    if current_user.role == "transport_company" and current_user.enterprise_id:
        v_in.enterprise_id = current_user.enterprise_id
    existing = db.query(Vehicle).filter(Vehicle.plate_number == v_in.plate_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="车牌号已存在")
    v = Vehicle(**v_in.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("", response_model=List[VehicleResponse])
def list_vehicles(
    status: Optional[VehicleStatus] = None,
    enterprise_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Vehicle).filter(Vehicle.is_active == True)
    if status:
        query = query.filter(Vehicle.status == status)
    if enterprise_id:
        query = query.filter(Vehicle.enterprise_id == enterprise_id)
    elif current_user.role == "transport_company" and current_user.enterprise_id:
        query = query.filter(Vehicle.enterprise_id == current_user.enterprise_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="车辆不存在")
    return v


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    v_in: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "transport_company")),
):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="车辆不存在")
    update_data = v_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return v


@router.post("/weighing/entry", response_model=WeighingRecordResponse)
async def weighing_entry(
    entry: WeighingEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "site_manager", "transport_company")),
):
    permit = None
    if entry.permit_id:
        permit = db.query(TransportPermit).filter(TransportPermit.id == entry.permit_id).first()
        if not permit:
            raise HTTPException(status_code=404, detail="准运证不存在")
        if permit.status not in [PermitStatus.ISSUED, PermitStatus.ACTIVE]:
            raise HTTPException(status_code=400, detail="准运证状态无效")

    record_code = f"WR{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}"
    record = WeighingRecord(
        record_code=record_code,
        permit_id=entry.permit_id,
        vehicle_id=entry.vehicle_id,
        construction_site_id=entry.construction_site_id,
        disposal_site_id=entry.disposal_site_id,
        tare_weight=entry.tare_weight,
        entry_images=entry.entry_images or [],
        status="loading",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if permit and permit.status == PermitStatus.ISSUED:
        permit.status = PermitStatus.ACTIVE
        db.commit()

    v = db.query(Vehicle).filter(Vehicle.id == entry.vehicle_id).first()
    if v:
        v.status = VehicleStatus.LOADING
        db.commit()

    return record


@router.post("/weighing/{record_id}/exit", response_model=WeighingRecordResponse)
async def weighing_exit(
    record_id: int,
    exit_data: WeighingExitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "site_manager")),
):
    record = db.query(WeighingRecord).filter(WeighingRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="称重记录不存在")
    if record.status != "loading":
        raise HTTPException(status_code=400, detail="称重状态不允许更新")

    record.gross_weight = exit_data.gross_weight
    record.exit_weight_time = datetime.utcnow()
    record.exit_images = exit_data.exit_images or []
    record.status = "in_transit"

    net = (record.gross_weight or 0) - (record.tare_weight or 0)
    record.net_weight = max(0, net)
    record.volume = max(0, net) / 1.5 if net > 0 else 0

    db.commit()
    db.refresh(record)

    await check_overload(db, record)

    v = db.query(Vehicle).filter(Vehicle.id == record.vehicle_id).first()
    if v:
        v.status = VehicleStatus.TRANSPORTING
        db.commit()

    return record


@router.post("/weighing/{record_id}/disposal-unload", response_model=WeighingRecordResponse)
async def disposal_unload(
    record_id: int,
    unload_data: Optional[DisposalUnloadUpdate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "disposal", "city_management")),
):
    record = db.query(WeighingRecord).filter(WeighingRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="称重记录不存在")
    if record.status not in ["in_transit", "unloading"]:
        raise HTTPException(status_code=400, detail="状态不允许执行消纳")

    now = datetime.utcnow()
    if unload_data:
        if unload_data.disposal_entry_time:
            record.disposal_entry_time = unload_data.disposal_entry_time
        else:
            if not record.disposal_entry_time:
                record.disposal_entry_time = now
        record.disposal_unload_time = unload_data.disposal_unload_time or now
    else:
        if not record.disposal_entry_time:
            record.disposal_entry_time = now
        record.disposal_unload_time = now
    record.status = "completed"
    db.commit()
    db.refresh(record)

    if record.permit_id:
        permit = db.query(TransportPermit).filter(TransportPermit.id == record.permit_id).first()
        if permit:
            permit.status = PermitStatus.USED
            permit.used_at = now
            db.commit()

    ds = db.query(DisposalSite).filter(DisposalSite.id == record.disposal_site_id).first()
    if ds and record.volume:
        new_remaining = max(0, ds.remaining_capacity - record.volume)
        new_accepted = ds.daily_accepted + record.volume
        try:
            report_disposal_capacity(db, ds.id, new_remaining, new_accepted, "auto")
        except Exception:
            ds.remaining_capacity = new_remaining
            ds.daily_accepted = new_accepted
            ds.last_update = now
            db.commit()

    v = db.query(Vehicle).filter(Vehicle.id == record.vehicle_id).first()
    if v:
        v.status = VehicleStatus.IDLE
        db.commit()

    return record


@router.get("/weighing/records", response_model=List[WeighingRecordResponse])
def list_weighing_records(
    construction_site_id: Optional[int] = None,
    disposal_site_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(WeighingRecord)
    if construction_site_id:
        query = query.filter(WeighingRecord.construction_site_id == construction_site_id)
    if disposal_site_id:
        query = query.filter(WeighingRecord.disposal_site_id == disposal_site_id)
    if vehicle_id:
        query = query.filter(WeighingRecord.vehicle_id == vehicle_id)
    if status:
        query = query.filter(WeighingRecord.status == status)
    if start_date:
        query = query.filter(WeighingRecord.entry_weight_time >= start_date)
    if end_date:
        query = query.filter(WeighingRecord.entry_weight_time <= end_date)
    return query.order_by(WeighingRecord.entry_weight_time.desc()).offset(skip).limit(limit).all()


@router.post("/track/point", response_model=TrackPointResponse)
async def submit_track_point(
    point: TrackPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "transport_company", "site_manager"
    )),
):
    track = TrackRecord(
        vehicle_id=point.vehicle_id,
        permit_id=point.permit_id,
        latitude=point.latitude,
        longitude=point.longitude,
        speed=point.speed,
        heading=point.heading,
        timestamp=datetime.utcnow(),
        gps_signal=point.gps_signal,
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    if point.permit_id:
        await check_route_deviation(db, track)
        permit = db.query(TransportPermit).filter(TransportPermit.id == point.permit_id).first()
        if permit and permit.status == PermitStatus.ACTIVE:
            await check_transport_timeout(db, permit)

    return track


@router.get("/track/history", response_model=List[TrackPointResponse])
def get_track_history(
    vehicle_id: Optional[int] = None,
    permit_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not vehicle_id and not permit_id:
        raise HTTPException(status_code=400, detail="必须提供vehicle_id或permit_id")
    query = db.query(TrackRecord)
    if vehicle_id:
        query = query.filter(TrackRecord.vehicle_id == vehicle_id)
    if permit_id:
        query = query.filter(TrackRecord.permit_id == permit_id)
    if start_time:
        query = query.filter(TrackRecord.timestamp >= start_time)
    if end_time:
        query = query.filter(TrackRecord.timestamp <= end_time)
    return query.order_by(TrackRecord.timestamp.asc()).offset(skip).limit(limit).all()
