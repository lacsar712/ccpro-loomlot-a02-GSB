from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.aux_dose import AuxDose
from app.models.dye_lot import DyeLot
from app.models.user import User
from app.models.vat import Vat
from app.schemas.aux_dose import AuxDoseCreate, AuxDoseOut

router = APIRouter(prefix="/api/aux-doses", tags=["aux-doses"])

# 同缸未排液期间，累计加注升数不得超过缸容的 30%
CAPACITY_RATIO = 0.30
# 染色中单次加注上限换算：最新染程布重 kg ÷ 2 = 加注上限 L（1kg 布对应 0.5L 助剂）
FABRIC_KG_TO_LITERS_DIVISOR = 2.0


def _accumulated_liters(db: Session, vat: Vat) -> float:
    """同缸自最近一次排液以来、未作废加注单的累计升数。"""
    q = db.query(func.coalesce(func.sum(AuxDose.liters), 0.0)).filter(
        AuxDose.vat_id == vat.id,
        AuxDose.voided_at.is_(None),
    )
    if vat.drained_at is not None:
        q = q.filter(AuxDose.dosed_at > vat.drained_at)
    return float(q.scalar() or 0.0)


@router.get("", response_model=List[AuxDoseOut])
def list_doses(
    vat_id: Optional[int] = Query(None, alias="vatId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(AuxDose)
    if vat_id is not None:
        q = q.filter(AuxDose.vat_id == vat_id)
    return q.order_by(AuxDose.id.desc()).all()


@router.post("", response_model=AuxDoseOut, status_code=status.HTTP_201_CREATED)
def create_dose(
    payload: AuxDoseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vat = db.query(Vat).filter(Vat.id == payload.vat_id).first()
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")

    # 仅染色中或就绪缸可加注；排液缸一律拒绝
    if vat.status == "drain":
        raise HTTPException(
            status_code=409,
            detail="染缸处于排液（drain）状态，不可加注；请重新开缸后再操作",
        )

    # 染色中：单次加注受同缸最新染程布重联锁（布重 kg ÷ 2 = 上限 L）
    if vat.status == "dyeing":
        latest_lot = (
            db.query(DyeLot)
            .filter(DyeLot.vat_id == vat.id)
            .order_by(DyeLot.started_at.desc(), DyeLot.id.desc())
            .first()
        )
        if latest_lot is not None:
            fabric_limit = latest_lot.fabric_kg / FABRIC_KG_TO_LITERS_DIVISOR
            if payload.liters > fabric_limit:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"单次加注 {payload.liters} 升超过染色中染缸布重联锁上限 "
                        f"{fabric_limit:g} 升（最新染程布重 {latest_lot.fabric_kg:g}kg；"
                        "换算约定：加注升数上限 = 布重千克 ÷ 2，即每 1kg 布最多加注 0.5L 助剂）"
                    ),
                )

    # 缸容约束：同缸未排液期间累计加注（含本次）不得超过缸容的 30%
    accumulated = _accumulated_liters(db, vat)
    capacity_limit = vat.capacity_l * CAPACITY_RATIO
    if accumulated + payload.liters > capacity_limit:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"同缸未排液期间已累计加注 {accumulated:g} 升，本次 {payload.liters:g} 升"
                    f"将超过缸容 {vat.capacity_l:g}L 的 30%（上限 {capacity_limit:g} 升）"
                ),
                "accumulatedLiters": round(accumulated, 4),
                "capacityLiters": vat.capacity_l,
                "limitLiters": round(capacity_limit, 4),
            },
        )

    item = AuxDose(
        vat_id=payload.vat_id,
        aux_name=payload.aux_name,
        liters=payload.liters,
        dosed_at=payload.dosed_at,
        operator_name=payload.operator_name,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{dose_id}/void", response_model=AuxDoseOut)
def void_dose(
    dose_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """作废加注单：仅主管（admin）可操作。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅染坊主管可作废加注单")
    item = db.query(AuxDose).filter(AuxDose.id == dose_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="加注单不存在")
    if item.voided_at is not None:
        raise HTTPException(status_code=400, detail="该加注单已作废")
    item.voided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{dose_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dose(
    dose_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """物理删除同样仅主管可操作，保持与作废一致的权限。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅染坊主管可删除加注单")
    item = db.query(AuxDose).filter(AuxDose.id == dose_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="加注单不存在")
    db.delete(item)
    db.commit()
