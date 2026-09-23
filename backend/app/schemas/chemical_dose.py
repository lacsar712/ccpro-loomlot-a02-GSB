from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChemicalDoseCreate(BaseModel):
    vat_id: int = Field(..., alias="vatId")
    chemical_name: str = Field(..., min_length=1, max_length=128, alias="chemicalName")
    dose_l: float = Field(..., gt=0, alias="doseL")
    dosed_at: datetime = Field(..., alias="dosedAt")
    operator_name: str = Field(..., min_length=1, max_length=64, alias="operatorName")

    model_config = ConfigDict(populate_by_name=True)


class ChemicalDoseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    vat_id: int = Field(serialization_alias="vatId")
    chemical_name: str = Field(serialization_alias="chemicalName")
    dose_l: float = Field(serialization_alias="doseL")
    dosed_at: datetime = Field(serialization_alias="dosedAt")
    operator_name: str = Field(serialization_alias="operatorName")
    voided: bool = False
    voided_at: Optional[datetime] = Field(None, serialization_alias="voidedAt")
    voided_by_name: Optional[str] = Field(None, serialization_alias="voidedByName")
