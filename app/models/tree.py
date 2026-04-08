from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveInt, field_validator


class TreeBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str
    description: str | None = None
    is_public: bool = False

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Tree name cannot be empty")
        if len(value) > 255:
            raise ValueError("Tree name must be at most 255 characters long")
        return value


class TreeCreate(TreeBase):
    pass


class TreeUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = None
    description: str | None = None
    is_public: bool | None = None

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value:
            raise ValueError("Tree name cannot be empty")
        if len(value) > 255:
            raise ValueError("Tree name must be at most 255 characters long")
        return value


class TreeCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_id: PositiveInt


class TreeAccessGrantRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: str
    access_level: Literal["view", "edit"]


class TreeAccessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: PositiveInt
    email: str
    access_level: Literal["owner", "view", "edit"]


class TreeAccessGrantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: PositiveInt
    access_level: Literal["view", "edit"]


class TreeAccessRevokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str


class TreeRead(TreeBase):
    id: PositiveInt
    owner_id: PositiveInt | None = None
    created_at: datetime
    access_level: Literal["owner", "view", "edit"]


class TreeDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    deleted_persons: int
    deleted_relationships: int
    deleted_access_entries: int
