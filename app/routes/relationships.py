from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.security import get_current_user_id
from app.db.crud import crud
from app.db.database import db
from app.models.relationship import (
    RelationshipCreate,
    RelationshipCreateResponse,
    RelationshipDeleteResponse,
)
from app.services.permissions import ensure_same_tree_persons_access, ensure_tree_edit_access
from app.services.relationship_service import (
    RelationshipServiceError,
    RelationshipValidationError,
    relationship_service,
)

router = APIRouter(prefix="/relationships", tags=["relationships"])
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
RelationshipIdPath = Annotated[int, Path(gt=0)]


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


@router.delete("/{relationship_id}", response_model=RelationshipDeleteResponse)
async def delete_relationship(
    relationship_id: RelationshipIdPath,
    user_id: CurrentUserId,
):
    async with db.pool.acquire() as connection:
        async with connection.transaction():
            relationship = await crud.get_relationship(
                relationship_id,
                connection=connection,
            )
            if not relationship:
                raise HTTPException(status_code=404, detail="Relationship not found")

            await ensure_tree_edit_access(
                user_id,
                relationship["tree_id"],
                connection=connection,
            )

            try:
                deleted_count = await relationship_service.delete_relationship(
                    relationship_id=relationship_id,
                    connection=connection,
                )
            except RelationshipValidationError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except RelationshipServiceError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete relationship",
                ) from exc

    return RelationshipDeleteResponse(
        detail="Relationship deleted",
        deleted_relationships=deleted_count,
    )
