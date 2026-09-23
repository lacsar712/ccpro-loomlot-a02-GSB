from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuxDoseCreate(BaseModel):
    vat_id: int = Field(..., alias="vatId")
    aux_name: str = Field(..., min_length=1, max_length=128, alias="auxName")
    liters: float = Field(..., gt=0, alias="liters")
    dosed_at: datetime = Field(..., alias="dosedAt")
    operator_name: str = Field(..., min_length=1, max_length=64, alias="operatorName")

    model_config = ConfigDict(populate_by_name=True)


class AuxDoseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    vat_id: int = Field(serialization_alias="vatId")
    aux_name: str = Field(serialization_alias="auxName")
    liters: float
    dosed_at: datetime = Field(serialization_alias="dosedAt")
    operator_name: str = Field(serialization_alias="operatorName")
    voided_at: Optional[datetime] = Field(serialization_alias="voidedAt")
