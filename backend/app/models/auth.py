from pydantic import BaseModel

from app.db.models import User, Visibility


class LoginRequest(BaseModel):
    # Compared case-sensitively, like the stored email.
    email: str
    password: str


class UserOut(BaseModel):
    """The authenticated user as the client sees it: no credential material."""
    id: str
    company_id: str
    first_name: str
    last_name: str
    email: str
    job_title: str
    visibility: Visibility

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        # password_hash and salt are not declared above, so they are never copied.
        return cls.model_validate(user, from_attributes=True)
