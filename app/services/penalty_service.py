from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import (
    Penalty, PenaltyStatus, Violation, WorkOrder, Enterprise, CreditRecord,
    TransportPermit, Vehicle
)
from ..utils.id_generator import generate_ticket_number
from ..services.notification_service_crud import send_notification
from ..models.notification import NotificationType


def _calculate_fine(violation_type: str, overload_pct: float = 0) -> float:
    fine_map = {
        "overload": 500 + overload_pct * 20,
        "unsealed": 2000,
        "off_route": 1000,
        "overtime": 500,
        "no_permit": 10000,
        "expired_permit": 5000,
    }
    return fine_map.get(violation_type, 1000)


def suggest_penalty_from_violation(
    db: Session, violation_id: int
) -> Optional[Penalty]:
    violation = db.query(Violation).filter(Violation.id == violation_id).first()
    if not violation:
        return None

    enterprise_id = None
    vehicle_id = None

    if violation.weighing_record_id:
        from ..models.transport import WeighingRecord
        wr = db.query(WeighingRecord).filter(WeighingRecord.id == violation.weighing_record_id).first()
        if wr:
            vehicle_id = wr.vehicle_id
            vehicle = db.query(Vehicle).filter(Vehicle.id == wr.vehicle_id).first()
            if vehicle:
                enterprise_id = vehicle.enterprise_id
    elif violation.permit_id:
        permit = db.query(TransportPermit).filter(TransportPermit.id == violation.permit_id).first()
        if permit:
            vehicle_id = permit.vehicle_id
            vehicle = db.query(Vehicle).filter(Vehicle.id == permit.vehicle_id).first()
            if vehicle:
                enterprise_id = vehicle.enterprise_id
    elif violation.vehicle_id:
        vehicle_id = violation.vehicle_id
        vehicle = db.query(Vehicle).filter(Vehicle.id == violation.vehicle_id).first()
        if vehicle:
            enterprise_id = vehicle.enterprise_id

    if not enterprise_id:
        return None

    overload_pct = 0
    if violation.type.value == "overload" and violation.weighing_record_id:
        from ..models.transport import WeighingRecord
        wr = db.query(WeighingRecord).filter(WeighingRecord.id == violation.weighing_record_id).first()
        if wr:
            overload_pct = wr.overload_percentage

    deduction_map = {
        "minor": 2, "medium": 5, "major": 10, "critical": 20,
    }

    ticket_number = generate_ticket_number()
    penalty = Penalty(
        ticket_number=ticket_number,
        violation_id=violation.id,
        enterprise_id=enterprise_id,
        vehicle_id=vehicle_id,
        violation_type=violation.type.value,
        description=violation.description,
        fine_amount=_calculate_fine(violation.type.value, overload_pct),
        credit_deduction=deduction_map.get(violation.level.value, 2),
        status=PenaltyStatus.DRAFT,
    )
    return penalty


def create_penalty(
    db: Session,
    enterprise_id: int,
    vehicle_id: Optional[int],
    violation_type: str,
    description: Optional[str],
    fine_amount: float,
    credit_deduction: float = 0,
    violation_id: Optional[int] = None,
    submitter_id: Optional[int] = None,
) -> Penalty:
    ticket_number = generate_ticket_number()
    penalty = Penalty(
        ticket_number=ticket_number,
        violation_id=violation_id,
        enterprise_id=enterprise_id,
        vehicle_id=vehicle_id,
        violation_type=violation_type,
        description=description,
        fine_amount=fine_amount,
        credit_deduction=credit_deduction,
        status=PenaltyStatus.PENDING_APPROVAL,
        submitter_id=submitter_id,
        submitted_at=datetime.utcnow(),
    )
    db.add(penalty)
    db.commit()
    db.refresh(penalty)
    return penalty


def submit_penalty_for_approval(db: Session, penalty_id: int, submitter_id: int) -> Penalty:
    penalty = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not penalty:
        raise ValueError("处罚单不存在")
    if penalty.status != PenaltyStatus.DRAFT:
        raise ValueError("只有草稿状态可以提交审批")

    penalty.status = PenaltyStatus.PENDING_APPROVAL
    penalty.submitter_id = submitter_id
    penalty.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(penalty)
    return penalty


async def approve_penalty(
    db: Session, penalty_id: int, approver_id: int, remark: Optional[str] = None
) -> Penalty:
    penalty = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not penalty:
        raise ValueError("处罚单不存在")
    if penalty.status != PenaltyStatus.PENDING_APPROVAL:
        raise ValueError("只有待审批状态可以批准")

    penalty.status = PenaltyStatus.APPROVED
    penalty.approver_id = approver_id
    penalty.approved_at = datetime.utcnow()
    penalty.approval_remark = remark
    db.commit()
    db.refresh(penalty)

    if penalty.credit_deduction > 0:
        enterprise = db.query(Enterprise).filter(Enterprise.id == penalty.enterprise_id).first()
        if enterprise:
            old_score = enterprise.credit_score
            new_score = max(0, old_score - penalty.credit_deduction)
            enterprise.credit_score = new_score

            record = CreditRecord(
                enterprise_id=enterprise.id,
                score_before=old_score,
                score_change=-penalty.credit_deduction,
                score_after=new_score,
                reason=f"处罚扣分-{penalty.violation_type}",
                related_type="penalty",
                related_id=penalty.id,
                operator_id=approver_id,
            )
            db.add(record)
            db.commit()

    await send_notification(
        db,
        NotificationType.PENALTY_APPROVED,
        "处罚审批通过通知",
        f"您有新的处罚单：{penalty.ticket_number}，罚款金额：{penalty.fine_amount}元",
        enterprise_id=penalty.enterprise_id,
        related_type="penalty",
        related_id=penalty.id,
    )

    return penalty


def reject_penalty(
    db: Session, penalty_id: int, approver_id: int, reason: str
) -> Penalty:
    penalty = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not penalty:
        raise ValueError("处罚单不存在")

    penalty.status = PenaltyStatus.REJECTED
    penalty.approver_id = approver_id
    penalty.rejection_reason = reason
    db.commit()
    db.refresh(penalty)
    return penalty


async def publish_penalty(db: Session, penalty_id: int) -> Penalty:
    penalty = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not penalty:
        raise ValueError("处罚单不存在")
    if penalty.status != PenaltyStatus.APPROVED:
        raise ValueError("只有已批准状态可以发布")

    penalty.status = PenaltyStatus.PUBLISHED
    penalty.published_at = datetime.utcnow()
    db.commit()
    db.refresh(penalty)

    await send_notification(
        db,
        NotificationType.PENALTY_PUBLISHED,
        "电子罚单已发布",
        f"您有新的电子罚单：{penalty.ticket_number}，罚款：{penalty.fine_amount}元，请及时处理",
        enterprise_id=penalty.enterprise_id,
        related_type="penalty",
        related_id=penalty.id,
    )

    return penalty


def mark_penalty_paid(db: Session, penalty_id: int) -> Penalty:
    penalty = db.query(Penalty).filter(Penalty.id == penalty_id).first()
    if not penalty:
        raise ValueError("处罚单不存在")

    penalty.status = PenaltyStatus.PAID
    penalty.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(penalty)
    return penalty
