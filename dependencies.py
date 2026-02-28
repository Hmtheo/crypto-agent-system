"""
FastAPI dependency injection - auth and portfolio helpers
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, Portfolio
from auth import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def get_current_portfolio(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Portfolio:
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at)
    )
    portfolio = result.scalars().first()
    if not portfolio:
        portfolio = Portfolio(user_id=user.id)
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
    return portfolio
