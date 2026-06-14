from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from io import BytesIO

from ..database import get_db
from ..models import (
    Settlement, SettlementStatus, DailyReport, User,
)
from ..schemas.business import (
    SettlementGenerate, SettlementResponse, DailyReportResponse,
)
from ..utils.security import get_current_user, require_roles
from ..services.settlement_service import (
    generate_settlement, confirm_settlement,
    mark_settlement_billed, mark_settlement_paid, get_enterprise_settlements,
)
from ..services.report_service import (
    query_reports, aggregate_stats, export_stats_to_excel, generate_daily_report,
)

router = APIRouter(prefix="/business", tags=["结算与报表"])


@router.post("/settlements/generate", response_model=SettlementResponse)
def create_settlement(
    settlement_in: SettlementGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "transport_company", "construction_unit"
    )),
):
    try:
        return generate_settlement(
            db,
            enterprise_id=settlement_in.enterprise_id,
            construction_site_id=settlement_in.construction_site_id,
            period_start=settlement_in.period_start,
            period_end=settlement_in.period_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settlements", response_model=List[SettlementResponse])
def list_settlements(
    enterprise_id: Optional[int] = None,
    construction_site_id: Optional[int] = None,
    status: Optional[SettlementStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not enterprise_id and current_user.enterprise_id and current_user.role in [
        "construction_unit", "transport_company",
    ]:
        enterprise_id = current_user.enterprise_id
    return get_enterprise_settlements(
        db, enterprise_id, construction_site_id, status, skip, limit
    )


@router.get("/settlements/{settlement_id}", response_model=SettlementResponse)
def get_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="对账单不存在")
    return s


@router.post("/settlements/{settlement_id}/confirm", response_model=SettlementResponse)
async def confirm(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "city_management", "construction_unit", "transport_company"
    )),
):
    try:
        return await confirm_settlement(db, settlement_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settlements/{settlement_id}/mark-billed", response_model=SettlementResponse)
def mark_billed(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        return mark_settlement_billed(db, settlement_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settlements/{settlement_id}/mark-paid", response_model=SettlementResponse)
def mark_paid(
    settlement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    try:
        return mark_settlement_paid(db, settlement_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reports/daily", response_model=List[DailyReportResponse])
def list_daily_reports(
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return query_reports(db, start_date, end_date, None, skip, limit)


@router.get("/reports/daily/{report_id}", response_model=DailyReportResponse)
def get_daily_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(DailyReport).filter(DailyReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")
    return r


@router.post("/reports/daily/generate-today")
def generate_today_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "city_management")),
):
    report = generate_daily_report()
    return {"status": "success", "report_id": report.report_id}


@router.get("/reports/stats")
def get_statistics(
    start_date: datetime = Query(..., description="统计开始日期"),
    end_date: Optional[datetime] = Query(None, description="统计结束日期，默认当天"),
    district: Optional[str] = Query(None, description="按区域筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not end_date:
        end_date = datetime.utcnow()
    return aggregate_stats(db, start_date, end_date, district)


@router.get("/reports/export/excel")
def export_excel(
    start_date: datetime = Query(..., description="统计开始日期"),
    end_date: Optional[datetime] = Query(None, description="统计结束日期，默认当天"),
    district: Optional[str] = Query(None, description="按区域筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not end_date:
        end_date = datetime.utcnow()
    stats = aggregate_stats(db, start_date, end_date, district)
    excel_data = export_stats_to_excel(stats)

    filename = f"运营报表_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
    bio = BytesIO(excel_data)
    bio.seek(0)

    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
