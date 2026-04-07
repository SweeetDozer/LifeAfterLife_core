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
    token_type: Literal["bearer"]
