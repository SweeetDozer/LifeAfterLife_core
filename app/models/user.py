from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) > 255:
            raise ValueError("Email must be at most 255 characters long")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(value) > 128:
            raise ValueError("Password must be at most 128 characters long")
        if not value.strip():
            raise ValueError("Password cannot be empty")
        return value


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) > 255:
            raise ValueError("Email must be at most 255 characters long")
        return normalized


class UserRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str


class UserLoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"]


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Refresh token cannot be empty")
        if len(normalized) > 2048:
            raise ValueError("Refresh token is too long")
        return normalized


class AuthSessionActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
