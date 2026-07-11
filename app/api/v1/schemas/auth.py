import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class Credentials(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class RegisterRequest(Credentials):
    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 12 or len(value) > 128:
            raise ValueError("Password must be between 12 and 128 characters")
        if not all(
            re.search(pattern, value) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w\s]")
        ):
            raise ValueError(
                "Password must include lowercase, uppercase, number, and special characters"
            )
        return value


class LoginRequest(Credentials):
    pass


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
