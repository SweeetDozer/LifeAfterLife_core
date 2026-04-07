from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.db.crud import crud
from app.models.tree import TreeCreate

router = APIRouter(prefix="/trees", tags=["trees"])


@router.post("/")
async def create_tree(tree: TreeCreate, user_id: int = Depends(get_current_user_id)):
    tree_id = await crud.create_tree(
        user_id,
        tree.name,
        tree.description,
        tree.is_public,
    )
    return {"tree_id": tree_id}


@router.get("/")
async def get_trees(user_id: int = Depends(get_current_user_id)):
    return await crud.get_user_trees(user_id)
