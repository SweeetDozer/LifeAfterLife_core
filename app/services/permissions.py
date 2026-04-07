from fastapi import HTTPException

from app.db.crud import crud


async def ensure_tree_exists(tree_id: int):
    tree = await crud.get_tree(tree_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    return tree


async def ensure_tree_view_access(user_id: int, tree_id: int):
    tree = await ensure_tree_exists(tree_id)
    if not await crud.user_can_view_tree(user_id, tree_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return tree


async def ensure_tree_edit_access(user_id: int, tree_id: int):
    tree = await ensure_tree_exists(tree_id)
    if not await crud.user_can_edit_tree(user_id, tree_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return tree


async def ensure_person_view_access(user_id: int, person_id: int):
    person = await crud.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    await ensure_tree_view_access(user_id, person["tree_id"])
    return person


async def ensure_person_edit_access(user_id: int, person_id: int):
    person = await crud.get_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    await ensure_tree_edit_access(user_id, person["tree_id"])
    return person
