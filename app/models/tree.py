from typing import Optional

from pydantic import BaseModel


class TreeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
