from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import NotificationType, ParameterType


class AutomationExclusiveGroupResponse(BaseModel):
    id: int
    name: str
    label: str | None = None
    description: str | None = None
    capacity: int = 1
    active: bool = True
    automation_ids: list[int] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AutomationExclusiveGroupCreate(BaseModel):
    name: str = Field(..., max_length=120)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    capacity: int = Field(default=1, ge=1, le=20)
    active: bool = True


class AutomationSuccessTriggerResponse(BaseModel):
    id: int
    source_automation_id: int
    target_automation_id: int
    target_automation_name: str | None = None
    priority_override: int | None = None
    inherit_parent_parameters: bool = True
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AutomationBase(BaseModel):
    name: str = Field(..., max_length=120)
    label: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None
    bot_id: int
    repository_id: int
    default_priority: int = Field(default=5, ge=1, le=10)
    notification_type: Optional[NotificationType] = None
    active: bool = True
    exclusive_group_ids: list[int] = Field(default_factory=list)
    success_trigger_automation_ids: list[int] = Field(default_factory=list)
    default_parameters_json: Optional[dict] = None
    default_runtime_parameters_json: Optional[dict] = None


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
    exclusive_group_ids: Optional[list[int]] = None
    success_trigger_automation_ids: Optional[list[int]] = None
    default_parameters_json: Optional[dict] = None
    default_runtime_parameters_json: Optional[dict] = None


class AutomationResponse(AutomationBase):
    id: int
    bot_name: str | None = None
    repository_name: str | None = None
    exclusive_groups: list[AutomationExclusiveGroupResponse] = Field(default_factory=list)
    success_triggers: list[AutomationSuccessTriggerResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationRunnerCreate(BaseModel):
    runner_id: int


class AutomationRunnerResponse(BaseModel):
    id: int
    automation_id: int
    runner_id: int
    runner_name: str | None = None
    runner_label: str | None = None
    runner_status: str | None = None
    runner_enabled: bool | None = None
    created_at: datetime | None = None

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
    
