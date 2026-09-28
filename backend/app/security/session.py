"""
Server-side session management: the storage half of session-based auth.

The browser holds a random token in a cookie. The database holds only the
SHA-256 digest of that token: a copy of the database yields no usable session,
because a digest cannot be turned back into the token the cookie must present.
Every request looks its caller up from the `sessions` table.
"""

import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import AuthSession, User
from app.security.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


SESSION_COOKIE_NAME = "arol_session"

# Idle timeout: a session dies after this long without requests.
SESSION_IDLE_TTL = timedelta(hours=8)

# Sliding-window granularity. The deadline is pushed forward only when it
# would move by at least this much, so a burst of requests does not turn into
# a burst of writes (SQLite has a single writer).
SESSION_REFRESH_INTERVAL = timedelta(minutes=5)

# A throwaway hash used when the email is unknown: verifying against it takes
# as long as a real verification, so response time does not reveal whether an
# address is registered. Computed once at import.
_DUMMY_HASH, _DUMMY_SALT = hash_password("timing-equalizer")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(token: str) -> str:
    """
    The single place a token is turned into its stored form. create, resolve
    and destroy must all hash identically, or sessions would never be found.

    Plain SHA-256, no salt, no scrypt: the token carries 256 bits of entropy,
    so it cannot be brute-forced the way a human-chosen password can.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Verify a credential pair. Returns the user, or None on any failure.

    Deliberately one return value for three different failures — unknown
    email, user without a password, wrong password. Telling them apart would
    let an attacker enumerate which addresses are registered.

    scrypt is CPU-bound and would block the event loop for every other
    request: it runs in a worker thread.
    """
    user = (await db.exec(select(User).where(User.email == email))).one_or_none()

    if user is None or user.password_hash is None or user.salt is None:
        await asyncio.to_thread(verify_password, password, _DUMMY_HASH, _DUMMY_SALT)
        return None

    ok = await asyncio.to_thread(verify_password, password, user.password_hash, user.salt)
    return user if ok else None


async def create_session(db: AsyncSession, user: User) -> str:
    """
    Open a session for a user who has just proved their identity.

    Returns the raw token: it goes into the cookie and is never stored.
    """
    token = secrets.token_hex(32)   # 32 random bytes = 256 bits
    db.add(AuthSession(
        id=_digest(token),
        user_id=user.id,
        expires_at=_now() + SESSION_IDLE_TTL,
    ))
    await db.commit()
    logger.info("Session opened for %s.", user.id)
    return token


async def resolve_session(db: AsyncSession, token: str) -> User | None:
    """
    Turn the cookie token into the live user, refreshing the deadline.

    An expired session is deleted rather than merely rejected: leaving dead
    rows behind means the table only ever grows.
    """
    session = await db.get(AuthSession, _digest(token))
    if session is None:
        return None

    now = _now()
    if session.expires_at <= now:
        await db.delete(session)
        await db.commit()
        logger.info("Session of %s expired.", session.user_id)
        return None

    user = await db.get(User, session.user_id)
    if user is None:
        # The FK with CASCADE says this cannot happen; if it does, the
        # session is garbage.
        await db.delete(session)
        await db.commit()
        return None

    # Sliding window: this request counts as activity.
    new_expiry = now + SESSION_IDLE_TTL
    if new_expiry - session.expires_at >= SESSION_REFRESH_INTERVAL:
        session.expires_at = new_expiry
        db.add(session)
        await db.commit()

    return user


async def destroy_session(db: AsyncSession, token: str) -> None:
    """Logout. Idempotent: destroying an unknown session is not an error."""
    session = await db.get(AuthSession, _digest(token))
    if session is not None:
        await db.delete(session)
        await db.commit()
        logger.info("Session closed for %s.", session.user_id)
