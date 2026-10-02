from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.enums import ComplaintStatus, Role
from app.models.user import User
from app.schemas.complaint import StatsOut

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

OPEN_STATUSES = (ComplaintStatus.SUBMITTED, ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED)


@router.get("/stats", response_model=StatsOut, summary="Dashboard statistics (admin)")
def stats(admin: AdminUser, db: DbSession):
    by_status = {s.value: 0 for s in ComplaintStatus}
    for st, count in db.execute(select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)):
        by_status[st.value] = count

    by_priority = {
        p.value: c for p, c in db.execute(select(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority))
    }
    by_category = {
        name: c
        for name, c in db.execute(
            select(Category.name, func.count(Complaint.id))
            .join(Complaint, Complaint.category_id == Category.id, isouter=True)
            .group_by(Category.name)
            .order_by(Category.name)
        )
    }

    resolved = db.execute(
        select(Complaint.created_at, Complaint.resolved_at).where(Complaint.resolved_at.is_not(None))
    ).all()
    avg_hours = (
        round(sum((r - c).total_seconds() for c, r in resolved) / len(resolved) / 3600, 2) if resolved else None
    )
    avg_rating = db.scalar(select(func.avg(Complaint.rating)).where(Complaint.rating.is_not(None)))

    return StatsOut(
        total_complaints=sum(by_status.values()),
        open_complaints=sum(by_status[s.value] for s in OPEN_STATUSES),
        by_status=by_status,
        by_priority=by_priority,
        by_category=by_category,
        total_citizens=db.scalar(select(func.count(User.id)).where(User.role == Role.CITIZEN)) or 0,
        total_officers=db.scalar(select(func.count(User.id)).where(User.role == Role.OFFICER)) or 0,
        avg_resolution_hours=avg_hours,
        avg_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
    )
