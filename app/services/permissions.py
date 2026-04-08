from collections.abc import Sequence
from typing import Literal

from fastapi import HTTPException

from app.db.crud import crud


AccessMode = Literal["view", "edit"]


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


def _forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail="Access denied")


def _deduplicate_ids(person_ids: Sequence[int]) -> list[int]:
    unique_ids: list[int] = []
    seen: set[int] = set()

    for person_id in person_ids:
        if person_id in seen:
            continue
        seen.add(person_id)
        unique_ids.append(person_id)

    return unique_ids


async def ensure_tree_access(
    user_id: int,
    tree_id: int,
    *,
    access: AccessMode = "view",
    connection=None,
):
    tree = await crud.get_tree(tree_id, connection=connection)
    if not tree:
        raise _not_found("Tree not found")

    if access == "view":
        if not await crud.user_can_view_tree(user_id, tree_id, connection=connection):
            raise _not_found("Tree not found")
        return tree

    if access != "edit":
        raise ValueError(f"Unsupported access mode: {access}")

    if await crud.user_can_edit_tree(user_id, tree_id, connection=connection):
        return tree

    if await crud.user_can_view_tree(user_id, tree_id, connection=connection):
        raise _forbidden()

    raise _not_found("Tree not found")


async def ensure_tree_view_access(user_id: int, tree_id: int, connection=None):
    return await ensure_tree_access(
        user_id,
        tree_id,
        access="view",
        connection=connection,
    )


async def ensure_tree_edit_access(user_id: int, tree_id: int, connection=None):
    return await ensure_tree_access(
        user_id,
        tree_id,
        access="edit",
        connection=connection,
    )


async def ensure_tree_owner_access(user_id: int, tree_id: int, connection=None):
    tree = await crud.get_tree(tree_id, connection=connection)
    if not tree:
        raise _not_found("Tree not found")

    if tree.get("owner_id") == user_id:
        return tree

    if await crud.user_can_view_tree(user_id, tree_id, connection=connection):
        raise _forbidden()

    raise _not_found("Tree not found")


async def ensure_person_access(
    user_id: int,
    person_id: int,
    *,
    access: AccessMode = "view",
    connection=None,
):
    person = await crud.get_person(person_id, connection=connection)
    if not person:
        raise _not_found("Person not found")

    try:
        await ensure_tree_access(
            user_id,
            person["tree_id"],
            access=access,
            connection=connection,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise _not_found("Person not found") from exc
        raise

    return person


async def ensure_person_view_access(user_id: int, person_id: int, connection=None):
    return await ensure_person_access(
        user_id,
        person_id,
        access="view",
        connection=connection,
    )


async def ensure_person_edit_access(user_id: int, person_id: int, connection=None):
    return await ensure_person_access(
        user_id,
        person_id,
        access="edit",
        connection=connection,
    )


async def ensure_tree_persons_access(
    user_id: int,
    tree_id: int,
    person_ids: Sequence[int],
    *,
    access: AccessMode = "view",
    connection=None,
):
    await ensure_tree_access(
        user_id,
        tree_id,
        access=access,
        connection=connection,
    )

    persons_by_id: dict[int, dict] = {}
    for person_id in _deduplicate_ids(person_ids):
        person = await crud.get_tree_person(tree_id, person_id, connection=connection)
        if not person:
            raise _not_found("Person not found")
        persons_by_id[person_id] = person

    return [persons_by_id[person_id] for person_id in person_ids]


async def ensure_same_tree_persons_access(
    user_id: int,
    person_ids: Sequence[int],
    *,
    access: AccessMode = "view",
    connection=None,
):
    persons_by_id: dict[int, dict] = {}
    for person_id in _deduplicate_ids(person_ids):
        persons_by_id[person_id] = await ensure_person_access(
            user_id,
            person_id,
            access=access,
            connection=connection,
        )

    persons = [persons_by_id[person_id] for person_id in person_ids]
    tree_ids = {person["tree_id"] for person in persons_by_id.values()}
    if len(tree_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail="Persons must belong to same tree",
        )

    return persons
