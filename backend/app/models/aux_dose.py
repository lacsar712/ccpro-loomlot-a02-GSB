from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vat import Vat


class AuxDose(Base):
    """助剂加注单：一次向某染缸加注助剂的记录。"""

    __tablename__ = "aux_doses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)
    aux_name: Mapped[str] = mapped_column(String(128), nullable=False)
    liters: Mapped[float] = mapped_column(Float, nullable=False)
    dosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    vat: Mapped["Vat"] = relationship("Vat", back_populates="aux_doses")
