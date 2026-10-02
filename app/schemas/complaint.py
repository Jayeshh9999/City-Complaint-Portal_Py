from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ComplaintStatus, Priority
from app.schemas.category import CategoryOut
from app.schemas.user import UserBrief


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    location: str = Field(min_length=3, max_length=255)
    category_id: int
    priority: Priority = Priority.MEDIUM


class ComplaintUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    location: str | None = Field(default=None, min_length=3, max_length=255)
    category_id: int | None = None
    priority: Priority | None = None


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_no: str
    title: str
    description: str
    location: str
    priority: Priority
    status: ComplaintStatus
    category: CategoryOut
    citizen: UserBrief
    assigned_officer: UserBrief | None
    rating: int | None
    feedback: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class AssignRequest(BaseModel):
    officer_id: int
    remarks: str | None = Field(default=None, max_length=1000)


class StatusUpdate(BaseModel):
    status: ComplaintStatus
    remarks: str | None = Field(default=None, max_length=1000)


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=1000)


class CommentCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author: UserBrief
    message: str
    created_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: ComplaintStatus | None
    to_status: ComplaintStatus
    changed_by: UserBrief
    remarks: str | None
    created_at: datetime


class StatsOut(BaseModel):
    total_complaints: int
    open_complaints: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_category: dict[str, int]
    total_citizens: int
    total_officers: int
    avg_resolution_hours: float | None
    avg_rating: float | None
