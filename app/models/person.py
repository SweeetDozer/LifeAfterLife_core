from pydantic import BaseModel
from typing import Optional
from datetime import date

class PersonCreate(BaseModel):
    tree_id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    description: Optional[str] = None