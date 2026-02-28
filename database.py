"""
Database setup - SQLAlchemy async with SQLite
"""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Ensure data directory exists
Path("data").mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/app.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables on startup"""
    # Import models so Base knows about them
    import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
