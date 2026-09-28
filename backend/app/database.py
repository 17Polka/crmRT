"""
database.py — SQLAlchemy async engine + session factory.

Поддерживает:
1. PostgreSQL (production) через asyncpg
2. SQLite (local development / standalone fallback) через aiosqlite
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./crmrt.db"

DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("postgresql"):
    engine_kwargs["pool_pre_ping"] = True
elif DATABASE_URL.startswith("sqlite"):
    # SQLite не поддерживает pool_pre_ping в таком виде
    pass

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
