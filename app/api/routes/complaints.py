from fastapi import APIRouter, Depends, status

from app.api.deps import AdminUser, CitizenUser, CurrentUser, DbSession, PageParams
from app.models.enums import ComplaintStatus, Priority
from app.schemas.common import Page
from app.schemas.complaint import (
    AssignRequest,
    CommentCreate,
    CommentOut,
    ComplaintCreate,
    ComplaintOut,
    ComplaintUpdate,
    FeedbackCreate,
    HistoryOut,
    StatusUpdate,
)
from app.services import complaints as svc

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED, summary="File a new complaint (citizen)")
def create_complaint(data: ComplaintCreate, citizen: CitizenUser, db: DbSession):
    return svc.create_complaint(db, citizen, data)


@router.get(
    "",
    response_model=Page[ComplaintOut],
    summary="List complaints visible to the current user",
    description="Citizens see their own complaints, officers see complaints assigned to them, admins see all.",
)
def list_complaints(
    user: CurrentUser,
    db: DbSession,
    paging: PageParams = Depends(),
    status_filter: ComplaintStatus | None = None,
    category_id: int | None = None,
    priority: Priority | None = None,
    q: str | None = None,
):
    items, total = svc.list_complaints(
        db,
        user,
        status_filter=status_filter,
        category_id=category_id,
        priority=priority,
        q=q,
        offset=paging.offset,
        limit=paging.size,
    )
    return Page.build(items, total, paging.page, paging.size)


@router.get("/{complaint_id}", response_model=ComplaintOut, summary="Get a complaint")
def get_complaint(complaint_id: int, user: CurrentUser, db: DbSession):
    return svc.get_visible_complaint(db, complaint_id, user)


@router.patch("/{complaint_id}", response_model=ComplaintOut, summary="Edit a complaint before assignment (citizen)")
def update_complaint(complaint_id: int, data: ComplaintUpdate, user: CurrentUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, user)
    return svc.update_complaint(db, complaint, user, data)


@router.post("/{complaint_id}/cancel", response_model=ComplaintOut, summary="Cancel a complaint before assignment (citizen)")
def cancel_complaint(complaint_id: int, user: CurrentUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, user)
    return svc.cancel_complaint(db, complaint, user)


@router.post("/{complaint_id}/assign", response_model=ComplaintOut, summary="Assign or reassign an officer (admin)")
def assign_officer(complaint_id: int, data: AssignRequest, admin: AdminUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, admin)
    return svc.assign_officer(db, complaint, admin, data.officer_id, data.remarks)


@router.post("/{complaint_id}/status", response_model=ComplaintOut, summary="Update complaint status (assigned officer or admin)")
def update_status(complaint_id: int, data: StatusUpdate, user: CurrentUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, user)
    return svc.change_status(db, complaint, user, data.status, data.remarks)


@router.post("/{complaint_id}/feedback", response_model=ComplaintOut, summary="Rate a resolved complaint and close it (citizen)")
def submit_feedback(complaint_id: int, data: FeedbackCreate, user: CurrentUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, user)
    return svc.submit_feedback(db, complaint, user, data.rating, data.feedback)


@router.get("/{complaint_id}/history", response_model=list[HistoryOut], summary="Status timeline of a complaint")
def get_history(complaint_id: int, user: CurrentUser, db: DbSession):
    return svc.get_visible_complaint(db, complaint_id, user).history


@router.get("/{complaint_id}/comments", response_model=list[CommentOut], summary="List comments on a complaint")
def list_comments(complaint_id: int, user: CurrentUser, db: DbSession):
    return svc.get_visible_complaint(db, complaint_id, user).comments


@router.post(
    "/{complaint_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED, summary="Comment on a complaint"
)
def add_comment(complaint_id: int, data: CommentCreate, user: CurrentUser, db: DbSession):
    complaint = svc.get_visible_complaint(db, complaint_id, user)
    return svc.add_comment(db, complaint, user, data.message)
