from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import Message
from app.schemas.user import PasswordChange, Token, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Register a citizen account")
def register(data: UserRegister, db: DbSession):
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone,
        hashed_password=hash_password(data.password),
        role=Role.CITIZEN,
    )
    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=Token, summary="Log in and obtain a JWT access token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled")
    return Token(access_token=create_access_token(user.id, user.role.value), user=user)


@router.get("/me", response_model=UserOut, summary="Get the current user")
def me(user: CurrentUser):
    return user


@router.post("/change-password", response_model=Message, summary="Change the current user's password")
def change_password(data: PasswordChange, user: CurrentUser, db: DbSession):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return Message(detail="Password updated successfully")
