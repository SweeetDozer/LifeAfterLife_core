from fastapi import APIRouter, HTTPException, Header
from app.models.person import PersonCreate
from app.db.crud import crud
from app.core.security import get_user_by_token

router = APIRouter(prefix="/persons", tags=["persons"])


def get_current_user(token: str):
    user_id = get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


@router.post("/")
async def create_person(person: PersonCreate, token: str = Header()):
    user_id = get_current_user(token)

    # ПОКА без проверки доступа (добавить позже)
    person_id = await crud.create_person(
        person.tree_id,
        person.first_name,
        person.middle_name,
        person.last_name,
        person.birth_date,
        person.death_date,
        person.description
    )

    return {"person_id": person_id}


@router.get("/tree/{tree_id}")
async def get_persons(tree_id: int, token: str = Header()):
    user_id = get_current_user(token)

    persons = await crud.get_tree_persons(tree_id)
    return persons


@router.get("/{person_id}")
async def get_person(person_id: int, token: str = Header()):
    user_id = get_current_user(token)

    person = await crud.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Not found")

    return person