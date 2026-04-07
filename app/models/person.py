from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    field_validator,
    model_validator,
)


class PersonBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: str
    middle_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    death_date: date | None = None
    description: str | None = None
    photo_url: str | None = None
    gender: Literal["male", "female", "other"] | None = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        if not value:
            raise ValueError("First name cannot be empty")
        if len(value) > 100:
            raise ValueError("First name must be at most 100 characters long")
        return value

    @field_validator(
        "middle_name",
        "last_name",
        "description",
        "photo_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("middle_name", "last_name")
    @classmethod
    def validate_optional_names(cls, value: str | None) -> str | None:
        if value is not None and len(value) > 100:
            raise ValueError("Name fields must be at most 100 characters long")
        return value

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url(cls, value: str | None) -> str | None:
        if value is not None and len(value) > 500:
            raise ValueError("Photo URL must be at most 500 characters long")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.birth_date is not None
            and self.death_date is not None
            and self.death_date < self.birth_date
        ):
            raise ValueError("Death date cannot be earlier than birth date")
        return self


class PersonCreate(PersonBase):
    tree_id: PositiveInt


class PersonRead(PersonBase):
    id: PositiveInt
    tree_id: PositiveInt


class PersonCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: PositiveInt
