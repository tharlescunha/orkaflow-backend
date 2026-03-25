from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import NotificationType, ParameterType


class AutomationBase(BaseModel):
    name: str = Field(..., max_length=120)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    bot_id: int
    repository_id: int
    default_priority: int = Field(default=5, ge=1, le=10)
    notification_type: Optional[NotificationType] = None
    active: bool = True


class AutomationCreate(AutomationBase):
    pass


class AutomationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    bot_id: Optional[int] = None
    repository_id: Optional[int] = None
    default_priority: Optional[int] = Field(default=None, ge=1, le=10)
    notification_type: Optional[NotificationType] = None
    active: Optional[bool] = None


class AutomationResponse(AutomationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationRunnerCreate(BaseModel):
    runner_id: int


class AutomationRunnerResponse(BaseModel):
    id: int
    automation_id: int
    runner_id: int

    model_config = {"from_attributes": True}


class AutomationParameterBase(BaseModel):
    name: str = Field(..., max_length=100)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    type: ParameterType
    allowed_values: Optional[dict | list] = None
    default_value: Optional[str] = None
    required: bool = False
    order_index: int = 0


class AutomationParameterCreate(AutomationParameterBase):
    pass


class AutomationParameterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    type: Optional[ParameterType] = None
    allowed_values: Optional[dict | list] = None
    default_value: Optional[str] = None
    required: Optional[bool] = None
    order_index: Optional[int] = None


class AutomationParameterResponse(AutomationParameterBase):
    id: int
    automation_id: int

    model_config = {"from_attributes": True}
    