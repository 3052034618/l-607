from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import (
    Settlement, SettlementStatus, ConstructionSite, Enterprise,
    WeighingRecord, TrackRecord, TransportPermit, Vehicle
)
from ..config import settings
from ..utils.id_generator import generate_settlement_number
from ..utils.distance import haversine_distance
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType


def _calculate_transport_distance(
    db: Session, permit_id: int, construction_site_id: int, disposal_site_id: int
) -> float:
    tracks = (
        db.query(TrackRecord)
        .filter(TrackRecord.permit_id == permit_id)
        .order_by(TrackRecord.timestamp.asc())
        .all()
    )

    if len(tracks) >= 2:
        distance = 0.0
        for i in range(len(tracks) - 1):
            distance += haversine_distance(
                (tracks[i].latitude, tracks[i].longitude),
                (tracks[i + 1].latitude, tracks[i + 1].longitude),
            )
        return max(distance, 0.1)

    cs = db.query(ConstructionSite).filter(ConstructionSite.id == construction_site_id).first()
    from ..models.site import DisposalSite
    ds = db.query(DisposalSite).filter(DisposalSite.id == disposal_site_id).first()
    if cs and ds:
        return haversine_distance(
            (cs.latitude, cs.longitude), (ds.latitude, ds.longitude)
        ) * 2

    return 5.0


def generate_settlement(
    db: Session,
    enterprise_id: int,
    construction_site_id: int,
    period_start: datetime,
    period_end: datetime,
) -> Settlement:
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    construction_site = db.query(ConstructionSite).filter(
        ConstructionSite.id == construction_site_id
    ).first()

    if not enterprise or not construction_site:
        raise ValueError("企业或工地不存在")

    records = (
        db.query(WeighingRecord)
        .join(TransportPermit, WeighingRecord.permit_id == TransportPermit.id)
        .join(Vehicle, TransportPermit.vehicle_id == Vehicle.id)
        .filter(
            WeighingRecord.status == "completed",
            WeighingRecord.construction_site_id == construction_site_id,
            Vehicle.enterprise_id == enterprise_id,
            WeighingRecord.exit_weight_time >= period_start,
            WeighingRecord.exit_weight_time <= period_end,
        )
        .all()
    )

    total_trips = len(records)
    total_volume = sum(r.volume or 0 for r in records)
    total_distance = 0.0
    transport_cost = 0.0
    disposal_cost = 0.0
    detail = []

    from ..models.penalty import Penalty, PenaltyStatus

    penalties = (
        db.query(Penalty)
        .filter(
            Penalty.enterprise_id == enterprise_id,
            Penalty.created_at >= period_start,
            Penalty.created_at <= period_end,
            Penalty.status.in_([PenaltyStatus.APPROVED, PenaltyStatus.PUBLISHED, PenaltyStatus.PAID]),
        )
        .all()
    )
    penalty_deduction = sum(p.fine_amount for p in penalties)

    for r in records:
        if r.permit_id:
            dist = _calculate_transport_distance(
                db, r.permit_id, r.construction_site_id, r.disposal_site_id
            )
            total_distance += dist
            vol = r.volume or 0
            transport_cost += vol * dist * settings.TRANSPORT_COST_PER_CUBIC_PER_KM
            disposal_cost += vol * settings.DISPOSAL_COST_PER_CUBIC

            detail.append({
                "permit_id": r.permit_id,
                "volume": vol,
                "distance": round(dist, 2),
                "transport_cost": round(vol * dist * settings.TRANSPORT_COST_PER_CUBIC_PER_KM, 2),
                "disposal_cost": round(vol * settings.DISPOSAL_COST_PER_CUBIC, 2),
            })

    total_amount = transport_cost + disposal_cost - penalty_deduction

    cs_code = construction_site.site_code or f"CS{construction_site.id}"
    settlement = Settlement(
        settlement_number=generate_settlement_number(cs_code),
        enterprise_id=enterprise_id,
        construction_site_id=construction_site_id,
        period_start=period_start,
        period_end=period_end,
        total_trips=total_trips,
        total_volume=round(total_volume, 2),
        total_distance=round(total_distance, 2),
        transport_cost=round(transport_cost, 2),
        disposal_cost=round(disposal_cost, 2),
        penalty_deduction=round(penalty_deduction, 2),
        total_amount=round(total_amount, 2),
        status=SettlementStatus.DRAFT,
        detail_summary={
            "trips": total_trips,
            "penalties_count": len(penalties),
            "details": detail[:500],
        },
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement


async def confirm_settlement(
    db: Session, settlement_id: int, confirmer_id: int
) -> Settlement:
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise ValueError("对账单不存在")
    if settlement.status != SettlementStatus.DRAFT:
        raise ValueError("只有草稿状态可以确认")

    settlement.status = SettlementStatus.CONFIRMED
    settlement.confirmed_by = confirmer_id
    settlement.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(settlement)

    await send_notification(
        db,
        NotificationType.SETTLEMENT_CONFIRMED,
        "对账单已确认",
        f"对账单{settlement.settlement_number}已确认，总金额：{settlement.total_amount}元",
        enterprise_id=settlement.enterprise_id,
        related_type="settlement",
        related_id=settlement.id,
    )
    return settlement


def mark_settlement_billed(db: Session, settlement_id: int) -> Settlement:
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise ValueError("对账单不存在")
    settlement.status = SettlementStatus.BILLED
    db.commit()
    db.refresh(settlement)
    return settlement


def mark_settlement_paid(db: Session, settlement_id: int) -> Settlement:
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        raise ValueError("对账单不存在")
    settlement.status = SettlementStatus.PAID
    db.commit()
    db.refresh(settlement)
    return settlement


def get_enterprise_settlements(
    db: Session,
    enterprise_id: Optional[int] = None,
    construction_site_id: Optional[int] = None,
    status: Optional[SettlementStatus] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Settlement]:
    query = db.query(Settlement)
    if enterprise_id:
        query = query.filter(Settlement.enterprise_id == enterprise_id)
    if construction_site_id:
        query = query.filter(Settlement.construction_site_id == construction_site_id)
    if status:
        query = query.filter(Settlement.status == status)
    return query.order_by(Settlement.created_at.desc()).offset(skip).limit(limit).all()
