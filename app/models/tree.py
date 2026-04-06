from pydantic import BaseModel

class TreeCreate(BaseModel):
    name: str