from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.security import get_current_user_id
from app.models.person import PersonCreate, PersonCreateResponse, PersonRead
from app.services.person_service import PersonServiceError, person_service

router = APIRouter(prefix="/persons", tags=["persons"])
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
TreeIdPath = Annotated[int, Path(gt=0)]
PersonIdPath = Annotated[int, Path(gt=0)]


@router.post("/", response_model=PersonCreateResponse)
async def create_person(person: PersonCreate, user_id: CurrentUserId):
    try:
        person_id = await person_service.create_person(user_id, person)
    except PersonServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return PersonCreateResponse(person_id=person_id)


@router.get("/tree/{tree_id}", response_model=list[PersonRead])
async def get_persons(tree_id: TreeIdPath, user_id: CurrentUserId):
    return await person_service.get_tree_persons(user_id, tree_id)


@router.get("/{person_id}", response_model=PersonRead)
async def get_person(person_id: PersonIdPath, user_id: CurrentUserId):
    return await person_service.get_person(user_id, person_id)
