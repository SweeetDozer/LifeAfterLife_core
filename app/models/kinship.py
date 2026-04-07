from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class KinshipRelationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["parent", "child", "sibling", "spouse", "friend", "unknown"]
    to: PositiveInt


class KinshipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: list[PositiveInt] = Field(min_length=1)
    relations: list[KinshipRelationRead]
    result: str
    line: str
    lca: PositiveInt | None = None
