from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.chemical_dose import ChemicalDose
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def start_of_this_week(now: datetime) -> datetime:
    """本周口径：本周一 UTC 00:00:00（Monday=0）。看板与列表按同一时间戳求和。"""
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    week_start = start_of_this_week(now)
    doses_l_this_week = (
        db.query(func.coalesce(func.sum(ChemicalDose.dose_l), 0.0))
        .filter(ChemicalDose.voided.is_(False))
        .filter(ChemicalDose.dosed_at >= week_start)
        .scalar()
        or 0.0
    )
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
        doses_l_this_week=float(doses_l_this_week),
        week_start=week_start,
    )
