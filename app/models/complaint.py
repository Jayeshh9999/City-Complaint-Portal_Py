from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.category import Category
from app.models.enums import ComplaintStatus, Priority
from app.models.user import User


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(255))
    priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False, length=20), default=Priority.MEDIUM, index=True)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, native_enum=False, length=20), default=ComplaintStatus.SUBMITTED, index=True
    )

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)

    rating: Mapped[int | None] = mapped_column(default=None)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    category: Mapped[Category] = relationship(lazy="joined")
    citizen: Mapped[User] = relationship(foreign_keys=[citizen_id], lazy="joined")
    assigned_officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id], lazy="joined")

    history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint", order_by="ComplaintStatusHistory.id", cascade="all, delete-orphan"
    )
    comments: Mapped[list["ComplaintComment"]] = relationship(
        back_populates="complaint", order_by="ComplaintComment.id", cascade="all, delete-orphan"
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    from_status: Mapped[ComplaintStatus | None] = mapped_column(Enum(ComplaintStatus, native_enum=False, length=20), default=None)
    to_status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus, native_enum=False, length=20))
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    remarks: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    complaint: Mapped[Complaint] = relationship(back_populates="history")
    changed_by: Mapped[User] = relationship(lazy="joined")


class ComplaintComment(Base):
    __tablename__ = "complaint_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    complaint: Mapped[Complaint] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(lazy="joined")
