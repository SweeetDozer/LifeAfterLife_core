from fastapi import APIRouter, HTTPException, Header
from app.models.relationship import RelationshipCreate
from app.services.relationship_service import service
from app.core.security import get_user_by_token

router = APIRouter(prefix="/relationships", tags=["relationships"])


def get_current_user(token: str):
    user_id = get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


@router.post("/")
async def create_relationship(rel: RelationshipCreate, token: str = Header()):
    user_id = get_current_user(token)

    try:
        await service.create_relationship(
            rel.from_person_id,
            rel.to_person_id,
            rel.relationship_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}