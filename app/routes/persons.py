from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.core.security import get_current_user_id
from app.models.person import (
    PersonCreate,
    PersonCreateResponse,
    PersonDeleteResponse,
    PersonRead,
    PersonUpdate,
)
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


@router.patch("/{person_id}", response_model=PersonRead)
async def update_person(
    person_id: PersonIdPath,
    person_update: PersonUpdate,
    user_id: CurrentUserId,
):
    try:
        return await person_service.update_person(user_id, person_id, person_update)
    except PersonServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{person_id}", response_model=PersonDeleteResponse)
async def delete_person(person_id: PersonIdPath, user_id: CurrentUserId):
    try:
        return await person_service.delete_person(user_id, person_id)
    except PersonServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
