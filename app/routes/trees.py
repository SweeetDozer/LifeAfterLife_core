from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.core.security import get_current_user_id
from app.db.crud import crud
from app.models.tree import (
    TreeAccessGrantRequest,
    TreeAccessGrantResponse,
    TreeAccessRead,
    TreeAccessRevokeResponse,
    TreeAccessUpdateRequest,
    TreeAccessUpdateResponse,
    TreeCreate,
    TreeCreateResponse,
    TreeDeleteResponse,
    TreeRead,
    TreeUpdate,
)
from app.services.tree_access_service import tree_access_service
from app.services.tree_service import tree_service

router = APIRouter(prefix="/trees", tags=["trees"])
TreeIdPath = Annotated[int, Path(gt=0)]
UserIdPath = Annotated[int, Path(gt=0)]


@router.post("/", response_model=TreeCreateResponse)
async def create_tree(tree: TreeCreate, user_id: int = Depends(get_current_user_id)):
    tree_id = await crud.create_tree(
        user_id,
        tree.name,
        tree.description,
        tree.is_public,
    )
    return TreeCreateResponse(tree_id=tree_id)


@router.get("/", response_model=list[TreeRead])
async def get_trees(user_id: int = Depends(get_current_user_id)):
    return await crud.get_user_trees(user_id)


@router.patch("/{tree_id}", response_model=TreeRead)
async def update_tree(
    tree_id: TreeIdPath,
    tree_update: TreeUpdate,
    user_id: int = Depends(get_current_user_id),
):
    return await tree_service.update_tree(user_id, tree_id, tree_update)


@router.delete("/{tree_id}", response_model=TreeDeleteResponse)
async def delete_tree(tree_id: TreeIdPath, user_id: int = Depends(get_current_user_id)):
    return await tree_service.delete_tree(user_id, tree_id)


@router.get("/{tree_id}/access", response_model=list[TreeAccessRead])
async def get_tree_access(tree_id: TreeIdPath, user_id: int = Depends(get_current_user_id)):
    return await tree_access_service.list_access(user_id, tree_id)


@router.post("/{tree_id}/access", response_model=TreeAccessGrantResponse)
async def grant_tree_access(
    tree_id: TreeIdPath,
    payload: TreeAccessGrantRequest,
    user_id: int = Depends(get_current_user_id),
):
    return await tree_access_service.grant_access(
        user_id,
        tree_id,
        payload.email,
        payload.access_level,
    )


@router.patch("/{tree_id}/access/{target_user_id}", response_model=TreeAccessUpdateResponse)
async def update_tree_access(
    tree_id: TreeIdPath,
    target_user_id: UserIdPath,
    payload: TreeAccessUpdateRequest,
    user_id: int = Depends(get_current_user_id),
):
    return await tree_access_service.update_access(
        user_id,
        tree_id,
        target_user_id,
        payload.access_level,
    )


@router.delete("/{tree_id}/access/{target_user_id}", response_model=TreeAccessRevokeResponse)
async def revoke_tree_access(
    tree_id: TreeIdPath,
    target_user_id: UserIdPath,
    user_id: int = Depends(get_current_user_id),
):
    return await tree_access_service.revoke_access(user_id, tree_id, target_user_id)
