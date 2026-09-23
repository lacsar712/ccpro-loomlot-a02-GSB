from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.chemical_dose import ChemicalDose
from app.models.dye_lot import DyeLot
from app.models.user import User
from app.models.vat import Vat
from app.schemas.chemical_dose import ChemicalDoseCreate, ChemicalDoseOut

router = APIRouter(prefix="/api/chemical-doses", tags=["chemical-doses"])

# 未排液期间，累计加注量不得超过缸容的 30%
CAPACITY_RATIO = 0.30
# 染程中单次加注上限：最新染程布重(kg)的一半。
# 换算约定：1 kg 布重折合 1 升助剂加注液，故单笔升数上限 = fabricKg * 0.5
FABRIC_KG_TO_LITER = 1.0
SINGLE_DOSE_RATIO = 0.5

DOSEABLE_STATUSES = {"ready", "dyeing"}
_EPS = 1e-9


def _accumulated_l(db: Session, vat: Vat) -> float:
    """同缸自上次排液以来、未作废加注单的累计升数。"""
    q = db.query(func.coalesce(func.sum(ChemicalDose.dose_l), 0.0)).filter(
        ChemicalDose.vat_id == vat.id,
        ChemicalDose.voided.is_(False),
    )
    if vat.last_drained_at is not None:
        q = q.filter(ChemicalDose.dosed_at > vat.last_drained_at)
    return float(q.scalar() or 0.0)


@router.get("", response_model=List[ChemicalDoseOut])
def list_doses(
    vat_id: Optional[int] = Query(None, alias="vatId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(ChemicalDose)
    if vat_id is not None:
        q = q.filter(ChemicalDose.vat_id == vat_id)
    return q.order_by(ChemicalDose.id.desc()).all()


@router.post("", response_model=ChemicalDoseOut, status_code=status.HTTP_201_CREATED)
def create_dose(
    payload: ChemicalDoseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 锁定缸行，确保“校验缸容 → 写入”在同一事务内原子完成，杜绝超限加注成功。
    vat = (
        db.query(Vat)
        .filter(Vat.id == payload.vat_id)
        .with_for_update()
        .first()
    )
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")

    # 仅染程中或就绪缸可加注；排液缸 409。
    if vat.status not in DOSEABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"染缸状态为「{vat.status}」，排液缸不可加注",
        )

    # 染程中：单次加注不得超过最新染程布重(kg)的一半（1kg 折 1 升）。违者 400。
    if vat.status == "dyeing":
        latest_lot = (
            db.query(DyeLot)
            .filter(DyeLot.vat_id == vat.id)
            .order_by(DyeLot.started_at.desc(), DyeLot.id.desc())
            .first()
        )
        if latest_lot is not None:
            single_cap = latest_lot.fabric_kg * FABRIC_KG_TO_LITER * SINGLE_DOSE_RATIO
            if payload.dose_l > single_cap + _EPS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"单次加注 {payload.dose_l:g}L 超限：该缸最新染程布重 "
                        f"{latest_lot.fabric_kg:g}kg，按 1kg 布重折 1 升、单笔不超过一半换算，"
                        f"单次不得超过 {single_cap:g}L"
                    ),
                )

    # 缸容联锁：未排液期间累计加注（含本次）不得超过缸容的 30%。超出 409 并回显已累计升数。
    accumulated = _accumulated_l(db, vat)
    capacity_cap = vat.capacity_l * CAPACITY_RATIO
    projected = accumulated + payload.dose_l
    if projected > capacity_cap + _EPS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"加注超缸容上限：该缸未排液期间已累计加注 {accumulated:g}L，"
                f"本次 {payload.dose_l:g}L 后将达 {projected:g}L，"
                f"超过缸容 {vat.capacity_l:g}L 的 30%（{capacity_cap:g}L）"
            ),
        )

    item = ChemicalDose(
        vat_id=payload.vat_id,
        chemical_name=payload.chemical_name,
        dose_l=payload.dose_l,
        dosed_at=payload.dosed_at,
        operator_name=payload.operator_name,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{dose_id}", response_model=ChemicalDoseOut)
def get_dose(
    dose_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(ChemicalDose).filter(ChemicalDose.id == dose_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="助剂加注单不存在")
    return item


@router.post("/{dose_id}/void", response_model=ChemicalDoseOut)
def void_dose(
    dose_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """作废加注单：仅染坊主管可执行，操作员 403。作废不删除记录。"""
    item = db.query(ChemicalDose).filter(ChemicalDose.id == dose_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="助剂加注单不存在")
    if item.voided:
        raise HTTPException(status_code=400, detail="该加注单已作废")
    item.voided = True
    item.voided_at = datetime.now(timezone.utc)
    item.voided_by_name = admin.display_name or admin.username
    db.commit()
    db.refresh(item)
    return item
