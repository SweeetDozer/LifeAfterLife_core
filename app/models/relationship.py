from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveInt, model_validator


class RelationshipCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    from_person_id: PositiveInt
    to_person_id: PositiveInt
    relationship_type: Literal["parent", "spouse", "sibling", "friend"]

    @model_validator(mode="after")
    def validate_person_ids(self):
        if self.from_person_id == self.to_person_id:
            raise ValueError("Cannot relate person to themselves")
        return self


class RelationshipCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship_id: PositiveInt


class RelationshipDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    deleted_relationships: int
