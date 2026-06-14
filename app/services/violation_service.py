from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import (
    Violation, ViolationType, ViolationLevel,
    WeighingRecord, TrackRecord, TransportPermit, PermitStatus,
    WorkOrder, WorkOrderStatus, EnforcementTeam, Enterprise, CreditRecord, User
)
from ..config import settings
from ..utils.distance import calculate_path_deviation
from ..utils.id_generator import generate_work_order_number
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType


def _get_violation_level(violation_type: ViolationType, **kwargs) -> ViolationLevel:
    if violation_type == ViolationType.OVERLOAD:
        overload_pct = kwargs.get("overload_percentage", 0)
        if overload_pct >= 50:
            return ViolationLevel.CRITICAL
        elif overload_pct >= 30:
            return ViolationLevel.MAJOR
        elif overload_pct >= 10:
            return ViolationLevel.MEDIUM
        else:
            return ViolationLevel.MINOR

    if violation_type == ViolationType.UNSEALED:
        return ViolationLevel.MEDIUM

    if violation_type == ViolationType.OFF_ROUTE:
        distance = kwargs.get("distance", 0)
        if distance >= 2000:
            return ViolationLevel.MAJOR
        elif distance >= 1000:
            return ViolationLevel.MEDIUM
        else:
            return ViolationLevel.MINOR

    if violation_type == ViolationType.OVERTIME:
        hours = kwargs.get("overtime_hours", 0)
        if hours >= 4:
            return ViolationLevel.MAJOR
        elif hours >= 2:
            return ViolationLevel.MEDIUM
        else:
            return ViolationLevel.MINOR

    if violation_type == ViolationType.NO_PERMIT:
        return ViolationLevel.CRITICAL

    if violation_type == ViolationType.EXPIRED_PERMIT:
        return ViolationLevel.MAJOR

    return ViolationLevel.MINOR


def _get_level_deduction(level: ViolationLevel) -> float:
    return {
        ViolationLevel.MINOR: settings.CREDIT_DEDUCTION_MINOR,
        ViolationLevel.MEDIUM: settings.CREDIT_DEDUCTION_MEDIUM,
        ViolationLevel.MAJOR: settings.CREDIT_DEDUCTION_MAJOR,
        ViolationLevel.CRITICAL: settings.CREDIT_DEDUCTION_CRITICAL,
    }.get(level, 0)


def create_violation(
    db: Session,
    violation_type: ViolationType,
    description: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    permit_id: Optional[int] = None,
    weighing_record_id: Optional[int] = None,
    location_lat: Optional[float] = None,
    location_lng: Optional[float] = None,
    is_auto_detected: bool = True,
    **kwargs,
) -> Violation:
    level = _get_violation_level(violation_type, **kwargs)
    deduction = _get_level_deduction(level)

    violation = Violation(
        violation_code=f"V{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        type=violation_type,
        level=level,
        description=description,
        vehicle_id=vehicle_id,
        permit_id=permit_id,
        weighing_record_id=weighing_record_id,
        location_lat=location_lat,
        location_lng=location_lng,
        detected_at=datetime.utcnow(),
        is_auto_detected=is_auto_detected,
    )
    db.add(violation)
    db.flush()

    order_number = generate_work_order_number(level.value)
    title = f"违规工单-{violation_type.value}"
    order = WorkOrder(
        order_number=order_number,
        violation_id=violation.id,
        title=title,
        description=description,
        priority=level,
        status=WorkOrderStatus.PENDING,
        credit_deduction=deduction,
    )
    db.add(order)
    db.commit()
    db.refresh(violation)
    db.refresh(order)

    return violation


async def check_overload(db: Session, weighing: WeighingRecord) -> Optional[Violation]:
    from ..models.vehicle import Vehicle

    vehicle = db.query(Vehicle).filter(Vehicle.id == weighing.vehicle_id).first()
    if not vehicle or not weighing.gross_weight or not weighing.tare_weight:
        return None

    net_weight = weighing.gross_weight - weighing.tare_weight
    overload_pct = 0
    if vehicle.load_capacity > 0:
        overload_pct = max(0, (net_weight - vehicle.load_capacity) / vehicle.load_capacity * 100)

    weighing.overload_percentage = overload_pct
    weighing.net_weight = net_weight
    weighing.volume = net_weight / 1.5 if net_weight > 0 else 0

    if overload_pct > 5:
        weighing.is_overloaded = True
        violation = create_violation(
            db,
            ViolationType.OVERLOAD,
            f"车辆{vehicle.plate_number}超载{overload_pct:.1f}%，核定载重{vehicle.load_capacity}吨，实际载重{net_weight:.2f}吨",
            vehicle_id=weighing.vehicle_id,
            permit_id=weighing.permit_id,
            weighing_record_id=weighing.id,
            overload_percentage=overload_pct,
        )
        await send_notification(
            db,
            NotificationType.VIOLATION_ALERT,
            "超载违规告警",
            violation.description,
            enterprise_id=vehicle.enterprise_id,
            related_type="violation",
            related_id=violation.id,
        )
        return violation
    return None


async def check_sealed(db: Session, weighing: WeighingRecord, is_sealed: bool) -> Optional[Violation]:
    from ..models.vehicle import Vehicle

    vehicle = db.query(Vehicle).filter(Vehicle.id == weighing.vehicle_id).first()
    if not vehicle:
        return None

    weighing.is_sealed = is_sealed
    db.commit()

    if not is_sealed:
        violation = create_violation(
            db,
            ViolationType.UNSEALED,
            f"车辆{vehicle.plate_number}未密闭运输",
            vehicle_id=weighing.vehicle_id,
            permit_id=weighing.permit_id,
            weighing_record_id=weighing.id,
        )
        await send_notification(
            db,
            NotificationType.VIOLATION_ALERT,
            "未密闭运输告警",
            violation.description,
            enterprise_id=vehicle.enterprise_id,
            related_type="violation",
            related_id=violation.id,
        )
        return violation
    return None


async def check_route_deviation(db: Session, track: TrackRecord) -> Optional[Violation]:
    permit = db.query(TransportPermit).filter(TransportPermit.id == track.permit_id).first()
    if not permit or not permit.planned_route:
        return None

    route_points = [(p["lat"], p["lng"]) for p in permit.planned_route if "lat" in p and "lng" in p]
    if len(route_points) < 2:
        return None

    deviation = calculate_path_deviation((track.latitude, track.longitude), route_points)
    track.is_off_route = deviation > settings.OFF_ROUTE_THRESHOLD_METERS
    track.off_route_distance = deviation
    db.commit()

    if track.is_off_route:
        violation = create_violation(
            db,
            ViolationType.OFF_ROUTE,
            f"车辆偏离规划路线，偏离距离{deviation:.1f}米",
            vehicle_id=track.vehicle_id,
            permit_id=track.permit_id,
            location_lat=track.latitude,
            location_lng=track.longitude,
            distance=deviation,
        )
        return violation
    return None


async def check_transport_timeout(db: Session, permit: TransportPermit) -> Optional[Violation]:
    from ..models.vehicle import Vehicle

    if permit.status != PermitStatus.ACTIVE:
        return None

    vehicle = db.query(Vehicle).filter(Vehicle.id == permit.vehicle_id).first()
    if not vehicle:
        return None

    now = datetime.utcnow()
    valid_from = permit.valid_from
    elapsed_hours = (now - valid_from).total_seconds() / 3600

    if elapsed_hours > settings.MAX_TRANSPORT_HOURS:
        overtime_hours = elapsed_hours - settings.MAX_TRANSPORT_HOURS
        violation = create_violation(
            db,
            ViolationType.OVERTIME,
            f"运输超时，已用时{elapsed_hours:.1f}小时，超过规定{settings.MAX_TRANSPORT_HOURS}小时",
            vehicle_id=permit.vehicle_id,
            permit_id=permit.id,
            overtime_hours=overtime_hours,
        )
        await send_notification(
            db,
            NotificationType.VIOLATION_ALERT,
            "运输超时告警",
            violation.description,
            enterprise_id=vehicle.enterprise_id,
            related_type="violation",
            related_id=violation.id,
        )
        return violation
    return None


def assign_work_order(
    db: Session,
    order_id: int,
    team_id: int,
    assignee_id: Optional[int] = None,
) -> WorkOrder:
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise ValueError("工单不存在")

    team = db.query(EnforcementTeam).filter(EnforcementTeam.id == team_id).first()
    if not team:
        raise ValueError("执法队不存在")

    order.team_id = team_id
    order.assignee_id = assignee_id
    order.status = WorkOrderStatus.ASSIGNED
    order.assigned_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    return order


def auto_assign_work_order(db: Session, order: WorkOrder) -> WorkOrder:
    teams = (
        db.query(EnforcementTeam)
        .filter(EnforcementTeam.is_active == True)
        .all()
    )
    if not teams:
        return order

    team_workloads = {}
    for team in teams:
        pending_count = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.team_id == team.id,
                WorkOrder.status.in_([WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS]),
            )
            .count()
        )
        team_workloads[team.id] = pending_count / max(team.workload_weight, 0.1)

    best_team_id = min(team_workloads, key=team_workloads.get)
    return assign_work_order(db, order.id, best_team_id)


async def complete_work_order(
    db: Session,
    order_id: int,
    result: str,
    penalty_suggested: bool = False,
    credit_deduction: float = 0,
    operator_id: Optional[int] = None,
) -> WorkOrder:
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise ValueError("工单不存在")

    order.result = result
    order.penalty_suggested = penalty_suggested
    order.credit_deduction = credit_deduction
    order.status = WorkOrderStatus.RESOLVED
    order.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    violation = db.query(Violation).filter(Violation.id == order.violation_id).first()
    if violation and credit_deduction > 0:
        permit = db.query(TransportPermit).filter(TransportPermit.id == violation.permit_id).first()
        vehicle = None
        if permit:
            vehicle = db.query(__import__("..models.vehicle", fromlist=["Vehicle"]).Vehicle).filter(
                __import__("..models.vehicle", fromlist=["Vehicle"]).Vehicle.id == permit.vehicle_id
            ).first()
        if vehicle and vehicle.enterprise_id:
            enterprise = db.query(Enterprise).filter(Enterprise.id == vehicle.enterprise_id).first()
            if enterprise:
                old_score = enterprise.credit_score
                new_score = max(0, old_score - credit_deduction)
                enterprise.credit_score = new_score

                credit_record = CreditRecord(
                    enterprise_id=enterprise.id,
                    score_before=old_score,
                    score_change=-credit_deduction,
                    score_after=new_score,
                    reason=f"违规扣分-{violation.type.value}",
                    related_type="work_order",
                    related_id=order.id,
                    operator_id=operator_id,
                )
                db.add(credit_record)
                db.commit()

    return order
