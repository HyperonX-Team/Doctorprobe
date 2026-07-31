"""User endpoints: CRUD plus checkup listing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.checkup import Checkup
from app.models.user import User
from app.schemas.checkup import CheckupSummary
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Load a user by id or raise 404 with a consistent error body."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Create a new user and return the full profile."""
    try:
        user = User(**payload.model_dump())
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create user",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> User:
    """Fetch a user profile."""
    return await _get_user_or_404(db, user_id)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Partially update a user's profile fields."""
    user = await _get_user_or_404(db, user_id)
    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await db.commit()
        await db.refresh(user)
        return user
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update user",
        )


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete a user. Checkups are removed via cascade."""
    await _get_user_or_404(db, user_id)
    try:
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete user",
        )
    return {"detail": "User deleted"}


@router.get(
    "/{user_id}/checkups",
    response_model=list[CheckupSummary],
    response_model_exclude={"user_id"},
)
async def list_user_checkups(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Checkup]:
    """List a user's checkups (summaries only, newest first)."""
    await _get_user_or_404(db, user_id)
    result = await db.execute(
        select(Checkup)
        .where(Checkup.user_id == user_id)
        .order_by(Checkup.created_at.desc())
    )
    return list(result.scalars().all())
