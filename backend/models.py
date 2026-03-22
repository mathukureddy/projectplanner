from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TaskInlineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None
    duration_days: Optional[int] = Field(default=None, ge=0)
    assigned_to: Optional[str] = None
    status: str = "Not Started"
    percent_complete: int = Field(default=0, ge=0, le=100)
    predecessors: List[str] = Field(default_factory=list)
    parent_task_id: Optional[str] = None


class TaskBase(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None
    duration_days: Optional[int] = Field(default=None, ge=0)
    assigned_to: Optional[str] = None
    status: str = "Not Started"
    percent_complete: int = Field(default=0, ge=0, le=100)
    predecessors: List[str] = Field(default_factory=list)
    parent_task_id: Optional[str] = None


class TaskCreate(TaskBase):
    ...


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None
    duration_days: Optional[int] = Field(default=None, ge=0)
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    percent_complete: Optional[int] = Field(default=None, ge=0, le=100)
    predecessors: Optional[List[str]] = None
    parent_task_id: Optional[str] = None


class Task(TaskBase):
    id: str
    created_at: datetime
    updated_at: datetime
    hierarchy_level: Optional[int] = None
    child_count: Optional[int] = None
    rollup_percent_complete: Optional[int] = None
    rollup_status: Optional[str] = None
    earliest_start_day: Optional[int] = None
    earliest_finish_day: Optional[int] = None
    latest_start_day: Optional[int] = None
    latest_finish_day: Optional[int] = None
    slack_days: Optional[int] = None
    is_critical: Optional[bool] = None
    baseline_variance_days: Optional[int] = None


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "On Track"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None


class ProjectCreate(ProjectBase):
    ...


class ProjectCreateWithTasks(ProjectBase):
    tasks: List[TaskInlineCreate] = Field(min_length=1)


class ShareEntry(BaseModel):
    """Project sharing: email + role (Smartsheet-like coarse permissions)."""

    email: str
    role: str = "viewer"  # viewer | editor | admin

    @field_validator("role")
    @classmethod
    def role_must_be_known(cls, v: str) -> str:
        allowed = {"viewer", "editor", "admin"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class FormulaRule(BaseModel):
    name: str
    target_field: str
    expression: str
    enabled: bool = True


class GovernancePolicy(BaseModel):
    locked_fields: List[str] = Field(default_factory=list)
    restrict_locked_to_admin: bool = True


class IntegrationConfig(BaseModel):
    type: str  # webhook | slack | email
    enabled: bool = True
    endpoint: Optional[str] = None
    secret: Optional[str] = None
    settings: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None
    shares: Optional[List[ShareEntry]] = None
    formulas: Optional[List[FormulaRule]] = None
    governance: Optional[GovernancePolicy] = None
    integrations: Optional[List[IntegrationConfig]] = None


class AutomationRule(BaseModel):
    """
    Automation rules for project scheduling/collaboration.
    Kept intentionally small for MVP (backend-side enforcement is best-effort).
    """

    type: str
    enabled: bool = True


def _default_automations() -> List[AutomationRule]:
    return [
        AutomationRule(type="notify_on_completion", enabled=True),
        AutomationRule(type="overdue_alert", enabled=True),
    ]


class Project(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime
    baseline_variance_days: Optional[int] = None
    schedule_status: Optional[str] = None
    shares: List[ShareEntry] = Field(default_factory=list)
    automations: List[AutomationRule] = Field(default_factory=_default_automations)
    formulas: List[FormulaRule] = Field(default_factory=list)
    governance: GovernancePolicy = Field(default_factory=GovernancePolicy)
    integrations: List[IntegrationConfig] = Field(default_factory=list)


class CommentCreate(BaseModel):
    task_id: str
    author: str
    body: str = Field(..., min_length=1, max_length=8000)


class Comment(CommentCreate):
    id: str
    project_id: str
    created_at: datetime


class AttachmentOut(BaseModel):
    id: str
    project_id: str
    task_id: str
    filename: str
    content_type: str
    size: int
    uploaded_by: Optional[str] = None
    created_at: datetime


class Alert(BaseModel):
    id: str
    project_id: str
    task_id: Optional[str] = None
    title: str
    message: str
    severity: str = "info"
    read: bool = False
    kind: str = "user"
    created_at: datetime


class AlertReadPatch(BaseModel):
    read: bool = True


class UserAlertCreate(BaseModel):
    project_id: str
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=2000)
    task_id: Optional[str] = None


class BaselineSnapshotOut(BaseModel):
    status: str = "ok"
    updated_tasks: int
    project: Project


class CellHistoryEntry(BaseModel):
    id: str
    project_id: str
    task_id: str
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: str = "system"
    source: str = "manual"
    changed_at: datetime


class IntegrationEvent(BaseModel):
    id: str
    project_id: str
    integration_type: str
    event_type: str
    direction: str  # inbound | outbound
    payload: dict = Field(default_factory=dict)
    created_at: datetime
