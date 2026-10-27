"""Calendários: dias úteis, feriados e janelas proibidas."""
from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema


class CalendarBlackout(OrkaBaseSchema):
    label: str = Field(default="", max_length=120)
    start: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    weekdays: list[int] = []


class CalendarBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    active: bool = True
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    holidays: list[str] = []
    blackouts: list[CalendarBlackout] = []

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, value: list[int]):
        cleaned = sorted({int(v) for v in value})
        if any(v < 0 or v > 6 for v in cleaned):
            raise ValueError("Dia da semana inválido (0 = segunda ... 6 = domingo).")
        return cleaned


class CalendarCreate(CalendarBase):
    pass


class CalendarUpdate(CalendarBase):
    pass


class CalendarRead(CalendarBase):
    id: int
    weekdays_label: str
    schedules_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class CalendarImportRequest(OrkaBaseSchema):
    year: int = Field(..., ge=2000, le=2100)


class CalendarCheckResponse(OrkaBaseSchema):
    allowed: bool
    reason: str | None = None
    next_allowed_at: datetime | None = None
