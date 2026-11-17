import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def check_password_rules(password: str) -> str:
    """Password rules: 8-72 chars, at least one letter and one digit.
    (72 is bcrypt's limit: longer passwords would be silently truncated.)"""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(password.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one digit")
    return password


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(examples=["sara_dev"])
    full_name: str = Field(default="", max_length=100, examples=["Sara Khan"])
    password: str = Field(examples=["Secret123"])

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("Username must be 3-32 letters, digits or underscores")
        return value.lower()

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()

    _password = field_validator("password")(check_password_rules)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    password: str | None = None

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str | None) -> str | None:
        return check_password_rules(value) if value is not None else None


class UserPublic(ORMModel):
    """What other people may see about a user."""

    id: int
    username: str
    full_name: str


class UserMe(UserPublic):
    """What you see about yourself (adds email). Never includes the password hash."""

    email: EmailStr
    created_at: datetime
