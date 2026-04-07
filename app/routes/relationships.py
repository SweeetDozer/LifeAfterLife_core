from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.db.database import db
from app.models.relationship import RelationshipCreate, RelationshipCreateResponse
from app.services.permissions import ensure_same_tree_persons_access
from app.services.relationship_service import (
    RelationshipServiceError,
    RelationshipValidationError,
    relationship_service,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])
CurrentUserId = Annotated[int, Depends(get_current_user_id)]


@router.post("/", response_model=RelationshipCreateResponse)
async def create_relationship(
    rel: RelationshipCreate,
    user_id: CurrentUserId,
):
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            from_person, to_person = await ensure_same_tree_persons_access(
                user_id,
                [rel.from_person_id, rel.to_person_id],
                access="edit",
                connection=connection,
            )

            try:
                relationship_id = await relationship_service.create_relationship(
                    from_person=from_person,
                    to_person=to_person,
                    relationship_type=rel.relationship_type,
                    connection=connection,
                )
            except RelationshipValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RelationshipServiceError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create relationship",
                ) from exc

    return RelationshipCreateResponse(relationship_id=relationship_id)
