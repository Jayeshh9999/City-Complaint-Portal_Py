from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Categories"])


def _get_or_404(db, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


def _ensure_unique_name(db, name: str, exclude_id: int | None = None) -> None:
    existing = db.scalar(select(Category).where(Category.name.ilike(name)))
    if existing and existing.id != exclude_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with this name already exists")


@router.get("", response_model=list[CategoryOut], summary="List active categories (public)")
def list_categories(db: DbSession, include_inactive: bool = False):
    query = select(Category).order_by(Category.name)
    if not include_inactive:
        query = query.where(Category.is_active.is_(True))
    return db.scalars(query).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, summary="Create a category (admin)")
def create_category(data: CategoryCreate, _: AdminUser, db: DbSession):
    _ensure_unique_name(db, data.name)
    category = Category(name=data.name.strip(), description=data.description)
    db.add(category)
    db.commit()
    return category


@router.patch("/{category_id}", response_model=CategoryOut, summary="Update or deactivate a category (admin)")
def update_category(category_id: int, data: CategoryUpdate, _: AdminUser, db: DbSession):
    category = _get_or_404(db, category_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"]:
        _ensure_unique_name(db, changes["name"], exclude_id=category.id)
    for field, value in changes.items():
        if value is not None:
            setattr(category, field, value)
    db.commit()
    return category
