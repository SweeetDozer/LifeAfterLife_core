from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class GraphPathResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: list[PositiveInt] = Field(min_length=1)
