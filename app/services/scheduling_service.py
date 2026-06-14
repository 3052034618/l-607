from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import (
    DisposalSite, ConstructionSite, TransportPlan, PlanStatus,
    WeighingRecord, CapacityRecord
)
from ..config import settings
from ..utils.distance import haversine_distance
from ..schemas.site import DisposalSiteRecommendation


def _is_within_operating_hours(current_time: datetime, hours_config: Dict) -> bool:
    if not hours_config:
        return True
    try:
        weekday = current_time.strftime("%A").lower()
        if weekday not in hours_config:
            return False
        today_hours = hours_config[weekday]
        if not today_hours:
            return False
        current_minutes = current_time.hour * 60 + current_time.minute
        for slot in today_hours:
            start_parts = slot["start"].split(":")
            end_parts = slot["end"].split(":")
            start_min = int(start_parts[0]) * 60 + int(start_parts[1])
            end_min = int(end_parts[0]) * 60 + int(end_parts[1])
            if start_min <= current_minutes <= end_min:
                return True
        return False
    except Exception:
        return True


def _check_peak_hours_balance(
    db: Session,
    disposal_site: DisposalSite,
    planned_trips: int,
    planned_date: datetime,
) -> Tuple[bool, float]:
    date_start = planned_date.replace(hour=0, minute=0, second=0)
    date_end = planned_date.replace(hour=23, minute=59, second=59)

    planned_volume = (
        db.query(TransportPlan)
        .filter(
            TransportPlan.disposal_site_id == disposal_site.id,
            TransportPlan.planned_date >= date_start,
            TransportPlan.planned_date <= date_end,
            TransportPlan.status.in_([PlanStatus.APPROVED, PlanStatus.IN_PROGRESS]),
        )
        .all()
    )
    total_planned = sum(p.planned_volume for p in planned_volume)

    limit = disposal_site.daily_acceptance_limit or (disposal_site.total_capacity * 0.1)
    if total_planned >= limit:
        return False, 0.0

    available_ratio = max(0.0, 1.0 - (total_planned / limit if limit > 0 else 1.0))
    return True, available_ratio


def recommend_disposal_sites(
    db: Session,
    construction_site_id: int,
    planned_volume: float,
    planned_date: datetime,
    waste_type: Optional[str] = None,
    top_k: int = 5,
) -> List[DisposalSiteRecommendation]:
    construction = db.query(ConstructionSite).filter(ConstructionSite.id == construction_site_id).first()
    if not construction:
        return []

    disposal_sites = (
        db.query(DisposalSite)
        .filter(DisposalSite.is_active == True, DisposalSite.remaining_capacity > 0)
        .all()
    )

    recommendations = []
    now = planned_date or datetime.utcnow()

    for site in disposal_sites:
        if waste_type and site.restricted_types and waste_type in site.restricted_types:
            continue

        if site.remaining_capacity < planned_volume:
            capacity_score = (site.remaining_capacity / planned_volume) * 30
        else:
            capacity_score = 30.0 + min(20.0, (site.remaining_capacity - planned_volume) / planned_volume * 10)

        distance = haversine_distance(
            (construction.latitude, construction.longitude),
            (site.latitude, site.longitude),
        )
        if distance <= 5:
            distance_score = 40.0
        elif distance <= 15:
            distance_score = 40.0 - ((distance - 5) / 10) * 15
        elif distance <= 30:
            distance_score = 25.0 - ((distance - 15) / 15) * 10
        else:
            distance_score = max(0, 15.0 - (distance - 30))

        time_score = 0.0
        if _is_within_operating_hours(now, site.acceptance_hours):
            time_score += 15.0

        peak_ok, peak_ratio = _check_peak_hours_balance(db, site, planned_volume, now)
        if peak_ok:
            time_score += peak_ratio * 15.0

        total_score = capacity_score + distance_score + time_score

        transport_cost = planned_volume * distance * settings.TRANSPORT_COST_PER_CUBIC_PER_KM
        disposal_cost = planned_volume * settings.DISPOSAL_COST_PER_CUBIC
        estimated_cost = transport_cost + disposal_cost

        recommendations.append(
            DisposalSiteRecommendation(
                disposal_site_id=site.id,
                disposal_site_name=site.name,
                distance_km=round(distance, 2),
                remaining_capacity=site.remaining_capacity,
                capacity_score=round(capacity_score, 2),
                distance_score=round(distance_score, 2),
                time_score=round(time_score, 2),
                total_score=round(total_score, 2),
                estimated_cost=round(estimated_cost, 2),
            )
        )

    recommendations.sort(key=lambda x: x.total_score, reverse=True)
    return recommendations[:top_k]


def report_disposal_capacity(
    db: Session,
    disposal_site_id: int,
    remaining_capacity: float,
    daily_accepted: float = 0,
    source: str = "manual",
) -> CapacityRecord:
    site = db.query(DisposalSite).filter(DisposalSite.id == disposal_site_id).first()
    if not site:
        raise ValueError("消纳场不存在")

    old_remaining = site.remaining_capacity
    site.remaining_capacity = remaining_capacity
    site.daily_accepted = daily_accepted
    site.last_update = datetime.utcnow()

    record = CapacityRecord(
        disposal_site_id=disposal_site_id,
        remaining_capacity=remaining_capacity,
        daily_accepted=daily_accepted,
        reported_at=datetime.utcnow(),
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(site)
    db.refresh(record)
    return record


def balance_transport_allocation(
    db: Session,
    construction_site_id: int,
    requested_volume: float,
    planned_date: datetime,
) -> List[Dict[str, Any]]:
    construction = db.query(ConstructionSite).filter(ConstructionSite.id == construction_site_id).first()
    if not construction:
        return []

    recs = recommend_disposal_sites(
        db, construction_site_id, requested_volume, planned_date, top_k=10
    )

    if not recs:
        return []

    total_score = sum(r.total_score for r in recs)
    if total_score <= 0:
        return []

    allocations = []
    remaining_volume = requested_volume

    for rec in recs:
        site = db.query(DisposalSite).filter(DisposalSite.id == rec.disposal_site_id).first()
        if not site:
            continue

        weight = rec.total_score / total_score
        allocated = min(
            requested_volume * weight,
            site.remaining_capacity,
            (site.daily_acceptance_limit or site.remaining_capacity) - site.daily_accepted,
        )
        allocated = min(allocated, remaining_volume)

        if allocated > 0:
            allocations.append({
                "disposal_site_id": rec.disposal_site_id,
                "disposal_site_name": rec.disposal_site_name,
                "allocated_volume": round(allocated, 2),
                "allocation_ratio": round(allocated / requested_volume, 4),
                "distance_km": rec.distance_km,
                "estimated_cost": round(
                    allocated * rec.distance_km * settings.TRANSPORT_COST_PER_CUBIC_PER_KM
                    + allocated * settings.DISPOSAL_COST_PER_CUBIC,
                    2,
                ),
            })
            remaining_volume -= allocated

        if remaining_volume <= 0:
            break

    return allocations
