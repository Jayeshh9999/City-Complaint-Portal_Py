from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, DbSession, PageParams
from app.core.security import hash_password
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import UserBrief, UserCreateByAdmin, UserOut, UserUpdateByAdmin

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=Page[UserOut], summary="List users (admin)")
def list_users(
    admin: AdminUser,
    db: DbSession,
    paging: PageParams = Depends(),
    role: Role | None = None,
    is_active: bool | None = None,
    q: str | None = None,
):
    conditions = []
    if role:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(User.full_name.ilike(like), User.email.ilike(like)))
    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    items = db.scalars(select(User).where(*conditions).order_by(User.id).offset(paging.offset).limit(paging.size)).all()
    return Page.build(list(items), total, paging.page, paging.size)


@router.get("/officers", response_model=list[UserBrief], summary="List active officers for assignment (admin)")
def list_officers(admin: AdminUser, db: DbSession):
    return db.scalars(select(User).where(User.role == Role.OFFICER, User.is_active.is_(True)).order_by(User.full_name)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Create an officer or admin (admin)")
def create_user(data: UserCreateByAdmin, admin: AdminUser, db: DbSession):
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user's profile, role or status (admin)")
def update_user(user_id: int, data: UserUpdateByAdmin, admin: AdminUser, db: DbSession):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    changes = data.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("is_active") is False or ("role" in changes and changes["role"] != Role.ADMIN)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate or demote your own account")
    for field, value in changes.items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    return user
