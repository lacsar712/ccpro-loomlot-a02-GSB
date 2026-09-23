from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vat import Vat


class ChemicalDose(Base):
    """助剂加注单：同一染缸未排液期间的助剂加注记录，可作废（不可删除）。"""

    __tablename__ = "chemical_doses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)
    chemical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dose_l: Mapped[float] = mapped_column(Float, nullable=False)
    dosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False)

    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    vat: Mapped["Vat"] = relationship("Vat", back_populates="chemical_doses")
