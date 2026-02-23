from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.services.monitoring_service import MonitoringService

router = APIRouter()


@router.get("/realtime")
async def get_realtime(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = MonitoringService(db)
    data = service.get_realtime_metrics()
    return {"success": True, "data": data}


@router.get("/statistics")
async def get_statistics(
    days: int = Query(default=7, ge=1, le=90),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = MonitoringService(db)
    data = service.get_statistics(days=days)
    return {"success": True, "data": data}


@router.get("/export")
async def export_report(
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = MonitoringService(db)
    csv_content = service.export_csv(start_date, end_date)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sessions_report.csv"},
    )
