import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.types import utcnow
from app.models.category import Category
from app.models.complaint import Complaint, ComplaintComment, ComplaintStatusHistory
from app.models.enums import ComplaintStatus as S
from app.models.enums import Priority, Role
from app.models.user import User
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate

# Allowed workflow transitions. ASSIGNED is entered only through the assign endpoint.
ALLOWED_TRANSITIONS: dict[S, set[S]] = {
    S.SUBMITTED: {S.ASSIGNED, S.REJECTED, S.CANCELLED},
    S.ASSIGNED: {S.IN_PROGRESS, S.REJECTED},
    S.IN_PROGRESS: {S.RESOLVED, S.REJECTED},
    S.RESOLVED: {S.CLOSED, S.IN_PROGRESS},
    S.CLOSED: set(),
    S.REJECTED: set(),
    S.CANCELLED: set(),
}
OFFICER_TARGETS = {S.IN_PROGRESS, S.RESOLVED, S.REJECTED}
REMARKS_REQUIRED = {S.RESOLVED, S.REJECTED}
REASSIGNABLE = {S.SUBMITTED, S.ASSIGNED, S.IN_PROGRESS}


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")


def _transition(db: Session, complaint: Complaint, to_status: S, actor: User, remarks: str | None = None) -> None:
    previous = complaint.status
    db.add(
        ComplaintStatusHistory(
            complaint=complaint, from_status=previous, to_status=to_status, changed_by=actor, remarks=remarks
        )
    )
    complaint.status = to_status
    if to_status == S.RESOLVED:
        complaint.resolved_at = utcnow()
    elif to_status == S.IN_PROGRESS:
        complaint.resolved_at = None


def get_visible_complaint(db: Session, complaint_id: int, user: User) -> Complaint:
    """Return the complaint if the user may see it; otherwise behave as if it does not exist."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise _not_found()
    if user.role == Role.ADMIN:
        return complaint
    if user.role == Role.OFFICER and complaint.assigned_officer_id == user.id:
        return complaint
    if user.role == Role.CITIZEN and complaint.citizen_id == user.id:
        return complaint
    raise _not_found()


def create_complaint(db: Session, citizen: User, data: ComplaintCreate) -> Complaint:
    category = db.get(Category, data.category_id)
    if category is None or not category.is_active:
        raise HTTPException(422, "Invalid or inactive category")

    complaint = Complaint(
        ticket_no=uuid.uuid4().hex,
        title=data.title,
        description=data.description,
        location=data.location,
        priority=data.priority,
        status=S.SUBMITTED,
        category=category,
        citizen=citizen,
    )
    db.add(complaint)
    db.flush()
    complaint.ticket_no = f"CCP-{complaint.created_at.year}-{complaint.id:06d}"
    db.add(
        ComplaintStatusHistory(
            complaint=complaint, from_status=None, to_status=S.SUBMITTED, changed_by=citizen, remarks="Complaint submitted"
        )
    )
    db.commit()
    return complaint


def list_complaints(
    db: Session,
    user: User,
    *,
    status_filter: S | None,
    category_id: int | None,
    priority: Priority | None,
    q: str | None,
    offset: int,
    limit: int,
) -> tuple[list[Complaint], int]:
    conditions = []
    if user.role == Role.CITIZEN:
        conditions.append(Complaint.citizen_id == user.id)
    elif user.role == Role.OFFICER:
        conditions.append(Complaint.assigned_officer_id == user.id)

    if status_filter:
        conditions.append(Complaint.status == status_filter)
    if category_id:
        conditions.append(Complaint.category_id == category_id)
    if priority:
        conditions.append(Complaint.priority == priority)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(
            or_(Complaint.title.ilike(like), Complaint.description.ilike(like), Complaint.ticket_no.ilike(like))
        )

    total = db.scalar(select(func.count(Complaint.id)).where(*conditions)) or 0
    items = db.scalars(
        select(Complaint).where(*conditions).order_by(Complaint.created_at.desc(), Complaint.id.desc()).offset(offset).limit(limit)
    ).unique().all()
    return list(items), total


def update_complaint(db: Session, complaint: Complaint, user: User, data: ComplaintUpdate) -> Complaint:
    if user.role != Role.CITIZEN or complaint.citizen_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the citizen who filed the complaint can edit it")
    if complaint.status != S.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "A complaint can be edited only before it is assigned")

    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes and changes["category_id"] is not None:
        category = db.get(Category, changes.pop("category_id"))
        if category is None or not category.is_active:
            raise HTTPException(422, "Invalid or inactive category")
        complaint.category = category
    else:
        changes.pop("category_id", None)
    for field, value in changes.items():
        if value is not None:
            setattr(complaint, field, value)
    db.commit()
    return complaint


def cancel_complaint(db: Session, complaint: Complaint, user: User) -> Complaint:
    if user.role != Role.CITIZEN or complaint.citizen_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the citizen who filed the complaint can cancel it")
    if S.CANCELLED not in ALLOWED_TRANSITIONS[complaint.status]:
        raise HTTPException(status.HTTP_409_CONFLICT, "A complaint can be cancelled only before it is assigned")
    _transition(db, complaint, S.CANCELLED, user, "Cancelled by citizen")
    db.commit()
    return complaint


def assign_officer(db: Session, complaint: Complaint, admin: User, officer_id: int, remarks: str | None) -> Complaint:
    if complaint.status not in REASSIGNABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A complaint in status {complaint.status.value} cannot be assigned")
    officer = db.get(User, officer_id)
    if officer is None or officer.role != Role.OFFICER or not officer.is_active:
        raise HTTPException(422, "Officer not found or inactive")

    complaint.assigned_officer = officer
    _transition(db, complaint, S.ASSIGNED, admin, remarks or f"Assigned to {officer.full_name}")
    db.commit()
    return complaint


def change_status(db: Session, complaint: Complaint, user: User, new_status: S, remarks: str | None) -> Complaint:
    is_assigned_officer = user.role == Role.OFFICER and complaint.assigned_officer_id == user.id
    if user.role != Role.ADMIN and not is_assigned_officer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not allowed to update this complaint")

    permitted_targets = OFFICER_TARGETS if user.role == Role.OFFICER else OFFICER_TARGETS | {S.CLOSED}
    if new_status not in permitted_targets:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You cannot set the status to {new_status.value} here")
    if new_status not in ALLOWED_TRANSITIONS[complaint.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot move a complaint from {complaint.status.value} to {new_status.value}"
        )
    if new_status in REMARKS_REQUIRED and not (remarks and remarks.strip()):
        raise HTTPException(422, f"Remarks are required when setting {new_status.value}")

    _transition(db, complaint, new_status, user, remarks)
    db.commit()
    return complaint


def submit_feedback(db: Session, complaint: Complaint, user: User, rating: int, feedback: str | None) -> Complaint:
    if user.role != Role.CITIZEN or complaint.citizen_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the citizen who filed the complaint can give feedback")
    if complaint.status != S.RESOLVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Feedback can be given only after the complaint is resolved")
    complaint.rating = rating
    complaint.feedback = feedback
    _transition(db, complaint, S.CLOSED, user, "Closed after citizen feedback")
    db.commit()
    return complaint


def add_comment(db: Session, complaint: Complaint, author: User, message: str) -> ComplaintComment:
    comment = ComplaintComment(complaint=complaint, author=author, message=message.strip())
    db.add(comment)
    db.commit()
    return comment
