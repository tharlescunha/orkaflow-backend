# app/domain/enums.py
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class RunnerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    BLOCKED = "blocked"


class BotTechnology(str, Enum):
    PYTHON = "python"
    JAVA = "java"
    NODE = "node"
    POWERSHELL = "powershell"
    OTHER = "other"


class BotSourceType(str, Enum):
    GIT = "git"
    ARTIFACT = "artifact"
    ZIP = "zip"
    MANUAL = "manual"


class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    JSON = "json"
    SELECT = "select"
    SECRET_REF = "secret_ref"


class TaskStatus(str, Enum):
    WAITING = "waiting"
    SCHEDULED = "scheduled"
    READY = "ready"
    RUNNING = "running"
    STOP_REQUESTED = "stop_requested"
    FORCED_STOP = "forced_stop"
    CANCELED = "canceled"
    FINISHED = "finished"
    ERROR = "error"
    TIMEOUT = "timeout"


class ExecutionMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RETRY = "retry"
    REPROCESS = "reprocess"
    API = "api"


class TaskLogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TaskLogSource(str, Enum):
    PANEL = "panel"
    SYSTEM = "system"
    WORKER = "worker"
    BACKEND = "backend"
    SCHEDULER = "scheduler"
    DISPATCHER = "dispatcher"


class ErrorCategory(str, Enum):
    TECHNICAL = "technical"
    BUSINESS = "business"
    TIMEOUT = "timeout"
    LOCK = "lock"
    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    NETWORK = "network"


class ScheduleType(str, Enum):
    CALENDAR = "calendar"
    CRON = "cron"


class CalendarType(str, Enum):
    ONCE = "once"
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class SchedulePolicy(str, Enum):
    CREATE_ALWAYS = "create_always"
    IGNORE_IF_RUNNING = "ignore_if_running"
    ENQUEUE_IF_NONE_PENDING = "enqueue_if_none_pending"
    RUN_IF_MISSED = "run_if_missed"
    SKIP_IF_MISSED = "skip_if_missed"


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"


class NotificationType(str, Enum):
    EMAIL = "email"
    PANEL = "panel"
    WEBHOOK = "webhook"


class LockScopeType(str, Enum):
    RUNNER = "runner"
    AUTOMATION = "automation"
    BOT = "bot"
    EXTERNAL_SYSTEM = "external_system"
    CREDENTIAL = "credential"
    BUSINESS_RESOURCE = "business_resource"


class CredentialValueType(str, Enum):
    STRING = "string"
    PASSWORD = "password"
    TOKEN = "token"
    JSON = "json"
    SECRET = "secret"

class BotExecutionMode(str, Enum):
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    