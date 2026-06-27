from app.schemas.auth import LoginRequest, MeResponse, RefreshTokenRequest, TokenResponse
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryListItem,
    RepositoryRead,
    RepositoryUpdate,
)

from app.schemas.user import (
    UserCreate,
    UserListItem,
    UserRead,
    UserUpdate,
)

from app.schemas.task import (
    TaskActionResponse,
    TaskCreate,
    TaskListItem,
    TaskListResponse,
    TaskManualCreateResponse,
    TaskParameterCreate,
    TaskParameterListResponse,
    TaskParameterRead,
    TaskRead,
    TaskStatusUpdate,
    TaskUpdate,
)

from app.schemas.task_log import (
    TaskLogCreate,
    TaskLogListItem,
    TaskLogListResponse,
    TaskLogRead,
)
from app.schemas.task_error import (
    TaskErrorCreate,
    TaskErrorListItem,
    TaskErrorListResponse,
    TaskErrorRead,
)
from app.schemas.bot import *
from app.schemas.bot_version import *
from app.schemas.automation import *
from app.schemas.schedule import *

__all__ = [
    "MessageResponse",
    "PaginatedResponse",
    "RepositoryCreate",
    "RepositoryListItem",
    "RepositoryRead",
    "RepositoryUpdate",
    "UserCreate",
    "UserListItem",
    "UserRead",
    "UserUpdate",
    "LoginRequest",
    "MeResponse",
    "RefreshTokenRequest",
    "TokenResponse",
    "TaskActionResponse",
    "TaskCreate",
    "TaskListItem",
    "TaskListResponse",
    "TaskManualCreateResponse",
    "TaskParameterCreate",
    "TaskParameterListResponse",
    "TaskParameterRead",
    "TaskRead",
    "TaskStatusUpdate",
    "TaskUpdate",
    "TaskLogCreate",
    "TaskLogListItem",
    "TaskLogListResponse",
    "TaskLogRead",
    "TaskErrorCreate",
    "TaskErrorListItem",
    "TaskErrorListResponse",
    "TaskErrorRead",
]
