from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentUser
from app.config import settings
from app.db.engine import get_session
from app.models.auth import LoginRequest, UserOut
from app.security.session import (
    SESSION_COOKIE_NAME,
    authenticate,
    create_session,
    destroy_session,
)

# The session is modelled as a resource: logging in CREATES a session,
# logging out DELETES the current one, "who am I" READS it.
router = APIRouter(prefix="/v1/sessions", tags=["auth"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def login(
    credentials: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await authenticate(db, credentials.email, credentials.password)
    if user is None:
        # One message for every failure: no hint about which part was wrong.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = await create_session(db, user)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,       # invisible to JavaScript: an XSS cannot read it
        samesite="lax",      # not sent on cross-site POSTs: basic CSRF protection
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
        # No max_age: a browser-session cookie. Expiry is enforced by the
        # server's sliding window; a fixed max_age would kill the cookie after
        # 8 hours even for a user who is still active.
    )
    return UserOut.from_model(user)


@router.get("/current", response_model=UserOut)
async def current_session(user: CurrentUser) -> UserOut:
    """Who am I. The frontend calls it on load to know if it is logged in."""
    return UserOut.from_model(user)


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_session),
) -> Response:
    """
    Idempotent: logging out without a session, or with an expired one, is not
    an error — the end state (no session) is the same.
    """
    if session_token is not None:
        await destroy_session(db, session_token)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response
