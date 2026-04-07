from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class PersonCreate(BaseModel):
    tree_id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    gender: Optional[Literal["male", "female", "other"]] = None
