from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
# Side-effect import: defining the table classes registers them on
# SQLModel.metadata, which create_all() reads. Nothing from the module is used
# by name, so the noqa stops linters from deleting it as "unused" — that would
# leave the metadata empty and create_all() would silently create no tables.
from app.db import models  # noqa: F401


# How long a connection waits for SQLite's write lock before giving up with
# "database is locked". SQLite allows a single writer at a time, and with the
# session sliding window every authenticated request performs a small write.
SQLITE_BUSY_TIMEOUT_MS = 5000


# The async engine: one per app, long-lived. sqlite+aiosqlite selects the
# SQLite dialect with the async aiosqlite driver. The engine opens no
# connection here: connections are opened lazily, on first use.
engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.DOMAIN_DB_PATH}",
    echo=False,  # True logs every SQL statement: useful when debugging queries
)


# Per-connection SQLite settings. PRAGMAs apply to a single connection, not to
# the database file, so they are issued on every new physical connection the
# pool opens. Connection-level events exist only on the sync engine that the
# async engine wraps, hence engine.sync_engine.
@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite_connection(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    # CRITICAL: foreign keys are OFF by default in SQLite. Without this,
    # ON DELETE RESTRICT / CASCADE and every FK constraint are silently ignored.
    cursor.execute("PRAGMA foreign_keys=ON")
    # Write-Ahead Log: readers no longer block the writer and vice versa.
    # Persistent in the file once set; creates the -wal and -shm side files.
    cursor.execute("PRAGMA journal_mode=WAL")
    # Wait for the write lock instead of failing immediately.
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.close()


# Session factory: produces short-lived AsyncSession objects bound to the
# engine above. A new session holds no connection until its first query.
# expire_on_commit=False keeps objects readable after commit: the default
# would reload expired attributes with an implicit query, which async
# SQLAlchemy forbids (MissingGreenlet).
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def create_db_and_tables() -> None:
    """
    Create the tables if they don't exist. Called once at startup (lifespan).

    SQLite creates the database file but not its parent directory, so the data
    directory is ensured first. The checkpoint DB lives in the same directory
    and is opened later in the lifespan, so this covers it too.

    create_all only creates MISSING tables: it never alters an existing one.
    A schema change requires deleting the DB file (or a migration tool).
    """
    Path(settings.DOMAIN_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        # create_all is a sync API: run_sync executes it on the async connection.
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency: one session per request.

    FastAPI runs this up to the yield, hands the session to the endpoint, and
    resumes after the response has been sent, closing it. Within one request
    the dependency is cached, so every dependant (e.g. both repositories)
    shares the same session. The `async with` guarantees the session is closed
    even if the endpoint raises, rolling back anything not committed.

    It never commits on its own: an endpoint that writes must commit
    explicitly, or its changes are discarded on close.
    """
    async with async_session_factory() as session:
        yield session