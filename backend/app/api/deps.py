from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.engine import get_session
from app.db.models import User
from app.security.access import may_use_chat
from app.security.session import SESSION_COOKIE_NAME, resolve_session


async def get_current_user(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_session),
) -> User:
    """
    The authentication gate. Any endpoint depending on this (directly or
    through another dependency) is closed to anonymous callers: a missing,
    unknown or expired cookie fails here with 401, before the endpoint runs.

    Within one request FastAPI caches this dependency, so the user is resolved
    once no matter how many dependencies ask for it.
    """
    unauthenticated = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
    if session_token is None:
        raise unauthenticated

    user = await resolve_session(db, session_token)
    if user is None:
        raise unauthenticated
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_chat_user(user: CurrentUser) -> User:
    """
    Authenticated AND allowed to use the assistant. Guests are rejected with
    403: they are authenticated (so not 401), and the restriction is a known
    property of their role, not a hidden resource (so not 404).
    """
    if not may_use_chat(user.visibility):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The assistant is not available to guest accounts",
        )
    return user


ChatUser = Annotated[User, Depends(get_chat_user)]
