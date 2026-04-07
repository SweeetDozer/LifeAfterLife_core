from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.db.crud import crud
from app.models.person import PersonCreate
from app.services.permissions import ensure_person_view_access, ensure_tree_edit_access, ensure_tree_view_access

router = APIRouter(prefix="/persons", tags=["persons"])


@router.post("/")
async def create_person(person: PersonCreate, user_id: int = Depends(get_current_user_id)):
    await ensure_tree_edit_access(user_id, person.tree_id)

    person_id = await crud.create_person(
        person.tree_id,
        person.first_name,
        person.middle_name,
        person.last_name,
        person.gender,
        person.birth_date,
        person.death_date,
        person.description,
        person.photo_url,
    )

    return {"person_id": person_id}


@router.get("/tree/{tree_id}")
async def get_persons(tree_id: int, user_id: int = Depends(get_current_user_id)):
    await ensure_tree_view_access(user_id, tree_id)
    return await crud.get_tree_persons(tree_id)


@router.get("/{person_id}")
async def get_person(person_id: int, user_id: int = Depends(get_current_user_id)):
    return await ensure_person_view_access(user_id, person_id)
