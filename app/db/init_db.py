import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (register models on metadata)
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.category import Category
from app.models.enums import Role
from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    ("Water Supply", "Shortage, leakage, contamination or billing of water supply"),
    ("Roads & Potholes", "Damaged roads, potholes, footpaths and road markings"),
    ("Street Lighting", "Non-working or damaged street lights"),
    ("Sanitation & Waste", "Garbage collection, overflowing bins and public cleanliness"),
    ("Drainage & Sewage", "Blocked drains, sewage overflow and waterlogging"),
    ("Public Transport", "Bus stops, routes and transport facilities"),
    ("Parks & Public Spaces", "Maintenance of parks, playgrounds and public areas"),
    ("Noise & Pollution", "Noise, air or water pollution complaints"),
    ("Other", "Any other municipal issue"),
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed_data(db: Session) -> None:
    if db.scalar(select(User.id).where(User.role == Role.ADMIN).limit(1)) is None:
        db.add(
            User(
                full_name=settings.first_admin_name,
                email=settings.first_admin_email.lower(),
                hashed_password=hash_password(settings.first_admin_password),
                role=Role.ADMIN,
            )
        )
        logger.info("Created initial admin account %s", settings.first_admin_email)

    if db.scalar(select(Category.id).limit(1)) is None:
        db.add_all(Category(name=name, description=desc) for name, desc in DEFAULT_CATEGORIES)
    db.commit()


def init_db() -> None:
    create_tables()
    with SessionLocal() as db:
        seed_data(db)
