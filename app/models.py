from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class InputMetadata(BaseModel):
    granularity: int
    startTime: int
    totalTimeSlots: int
    timezone: str
    currency: Optional[str] = Field(
        default=None,
        description="If set, echoed in output metadata; otherwise server default (INR).",
    )


class Rates(BaseModel):
    rateVector: list[float]


class TouWindow(BaseModel):
    type: str
    startHour: int = Field(ge=0, le=24)
    endHour: int = Field(ge=0, le=24)


class TouRates(BaseModel):
    offPeak: Optional[float] = None
    midPeak: Optional[float] = None
    onPeak: Optional[float] = None


class Tou(BaseModel):
    mapping: list[TouWindow]
    rates: TouRates


class AllowedWindow(BaseModel):
    startHour: int = Field(ge=0, le=24)
    endHour: int = Field(ge=0, le=24)


class BlockConstraints(BaseModel):
    maxShiftHours: Optional[int] = Field(default=None, ge=0)
    allowedWindows: Optional[list[AllowedWindow]] = None


class ApplianceBlock(BaseModel):
    blockId: int
    start_t: int = Field(ge=0)
    duration: int = Field(ge=1)
    consumption: list[float]
    constraints: Optional[BlockConstraints] = None

    @model_validator(mode="after")
    def consumption_len_matches_duration(self):
        if len(self.consumption) != self.duration:
            raise ValueError(
                f"consumption length ({len(self.consumption)}) must equal duration ({self.duration})"
            )
        return self


class Appliance(BaseModel):
    appId: int
    name: str
    shiftable: bool
    blocks: list[ApplianceBlock]


class OptimizeRequest(BaseModel):
    metadata: InputMetadata
    rates: Rates
    tou: Optional[Tou] = None
    appliances: list[Appliance]

    @model_validator(mode="after")
    def rate_vector_len(self):
        n = self.metadata.totalTimeSlots
        if len(self.rates.rateVector) != n:
            raise ValueError(
                f"rates.rateVector length ({len(self.rates.rateVector)}) must equal "
                f"metadata.totalTimeSlots ({n})"
            )
        for app in self.appliances:
            for b in app.blocks:
                if b.start_t + b.duration > n:
                    raise ValueError(
                        f"Block appId={app.appId} blockId={b.blockId}: start_t + duration "
                        f"({b.start_t + b.duration}) exceeds totalTimeSlots ({n})"
                    )
        return self


class OutputMetadata(BaseModel):
    granularity: int
    totalTimeSlots: int
    currency: str


class BlockShiftResult(BaseModel):
    blockId: int
    originalStart_t: int
    newStart_t: int
    duration: int
    consumption: list[float]
    costBefore: float
    costAfter: float
    savings: float


class ApplianceShiftResult(BaseModel):
    appId: int
    totalSavings: float
    blockShifts: list[BlockShiftResult]


class OptimizeResponse(BaseModel):
    metadata: OutputMetadata
    loadShift: list[ApplianceShiftResult]
