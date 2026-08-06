from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
# Importing models here ensures their tables are registered on SQLModel.metadata
# before create_all() runs. Without this import, metadata would be empty.
from app.db import models  


# The async engine: one per app, long-lived. sqlite+aiosqlite is the async driver.
engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.DOMAIN_DB_PATH}",
    echo=False,
)


# CRITICAL for SQLite: foreign keys are OFF by default and must be switched on
# per connection, or the ON DELETE RESTRICT / FK constraints are silently ignored.
@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Session factory: produces short-lived AsyncSession objects (one per request).
# expire_on_commit=False keeps objects usable after commit (so the endpoint can
# still read an object's fields after the session committed it).
_async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def create_db_and_tables() -> None:
    """Create the tables if they don't exist. Called once at startup (lifespan)."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency: opens a session for the duration of one request and
    closes it afterwards. Injected into endpoints/repositories via Depends,
    exactly like get_..._repository. The `async with` guarantees the session
    is closed even if the endpoint raises.
    """
    async with _async_session_factory() as session:
        yield session