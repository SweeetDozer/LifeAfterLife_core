from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.models.relationship import RelationshipCreate
from app.services.permissions import ensure_person_edit_access
from app.services.relationship_service import service

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.post("/")
async def create_relationship(
    rel: RelationshipCreate,
    user_id: int = Depends(get_current_user_id),
):
    await ensure_person_edit_access(user_id, rel.from_person_id)
    await ensure_person_edit_access(user_id, rel.to_person_id)

    try:
        relationship_id = await service.create_relationship(
            rel.from_person_id,
            rel.to_person_id,
            rel.relationship_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"relationship_id": relationship_id}
