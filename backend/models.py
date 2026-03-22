from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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


class IntakeFormField(BaseModel):
    """Single question on an intake form."""

    key: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)
    type: str = "text"  # text | textarea | email | number | date
    required: bool = False

    @field_validator("key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        k = (v or "").strip().lower()
        if not k.replace("_", "").isalnum():
            raise ValueError("key must be alphanumeric with underscores")
        return k

    @field_validator("type")
    @classmethod
    def type_known(cls, v: str) -> str:
        allowed = {"text", "textarea", "email", "number", "date"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class IntakeFormCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    enabled: bool = True
    fields: List[IntakeFormField] = Field(min_length=1)
    task_name_field: str
    task_description_field: Optional[str] = None
    task_assigned_to_field: Optional[str] = None
    task_start_date_field: Optional[str] = None
    task_end_date_field: Optional[str] = None
    default_status: str = "Not Started"

    @model_validator(mode="after")
    def mapping_keys_must_exist(self) -> "IntakeFormCreate":
        keys = {f.key for f in self.fields}
        if len(keys) != len(self.fields):
            raise ValueError("field keys must be unique")

        def _norm(k: Optional[str]) -> Optional[str]:
            if k is None or str(k).strip() == "":
                return None
            return str(k).strip().lower()

        name_f = _norm(self.task_name_field)
        if not name_f or name_f not in keys:
            raise ValueError("task_name_field must match a field key")

        for label, val in (
            ("task_description_field", _norm(self.task_description_field)),
            ("task_assigned_to_field", _norm(self.task_assigned_to_field)),
            ("task_start_date_field", _norm(self.task_start_date_field)),
            ("task_end_date_field", _norm(self.task_end_date_field)),
        ):
            if val is not None and val not in keys:
                raise ValueError(f"{label} must match a field key or be omitted")

        self.task_name_field = name_f
        self.task_description_field = _norm(self.task_description_field)
        self.task_assigned_to_field = _norm(self.task_assigned_to_field)
        self.task_start_date_field = _norm(self.task_start_date_field)
        self.task_end_date_field = _norm(self.task_end_date_field)
        return self


class IntakeFormUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    enabled: Optional[bool] = None
    fields: Optional[List[IntakeFormField]] = None
    task_name_field: Optional[str] = None
    task_description_field: Optional[str] = None
    task_assigned_to_field: Optional[str] = None
    task_start_date_field: Optional[str] = None
    task_end_date_field: Optional[str] = None
    default_status: Optional[str] = None


class IntakeFormOut(BaseModel):
    id: str
    project_id: str
    slug: str
    name: str
    enabled: bool
    fields: List[IntakeFormField]
    task_name_field: str
    task_description_field: Optional[str] = None
    task_assigned_to_field: Optional[str] = None
    task_start_date_field: Optional[str] = None
    task_end_date_field: Optional[str] = None
    default_status: str = "Not Started"
    created_at: datetime
    updated_at: datetime


class IntakeFormPublicOut(BaseModel):
    """Schema exposed to anonymous submitters (no internal ids)."""

    name: str
    fields: List[IntakeFormField]
    project_name: str


class IntakeSubmitPayload(BaseModel):
    responses: dict = Field(default_factory=dict)


class IntakeSubmissionOut(BaseModel):
    id: str
    form_id: str
    project_id: str
    task_id: str
    responses: dict = Field(default_factory=dict)
    submitted_at: datetime
