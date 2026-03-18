from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskInlineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
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


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None


class Project(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

