from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.aux_dose import AuxDose
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _week_start_utc(now: datetime) -> datetime:
    """本周一 00:00（UTC）。看板与列表的「本周」口径以此为准。"""
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    week_start = _week_start_utc(now)
    return DashboardStats(
        dye_house_total=db.query(func.count(DyeHouse.id)).scalar() or 0,
        vat_ready_count=db.query(func.count(Vat.id)).filter(Vat.status == "ready").scalar() or 0,
        vat_dyeing_count=db.query(func.count(Vat.id)).filter(Vat.status == "dyeing").scalar() or 0,
        lots_last_7d=(
            db.query(func.count(DyeLot.id))
            .filter(DyeLot.started_at >= now - timedelta(days=7))
            .scalar()
            or 0
        ),
        checks_last_24h=(
            db.query(func.count(FastnessCheck.id))
            .filter(FastnessCheck.checked_at >= now - timedelta(hours=24))
            .scalar()
            or 0
        ),
        aux_dose_liters_this_week=(
            db.query(func.coalesce(func.sum(AuxDose.liters), 0.0))
            .filter(AuxDose.dosed_at >= week_start, AuxDose.voided_at.is_(None))
            .scalar()
            or 0.0
        ),
    )
