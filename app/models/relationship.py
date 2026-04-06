from pydantic import BaseModel
from typing import Literal

class RelationshipCreate(BaseModel):
    from_person_id: int
    to_person_id: int
    relationship_type: Literal["parent", "spouse", "sibling", "friend"]