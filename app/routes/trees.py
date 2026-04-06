from fastapi import APIRouter, HTTPException, Header
from app.models.tree import TreeCreate
from app.db.crud import crud
from app.core.security import get_user_by_token

router = APIRouter(prefix="/trees", tags=["trees"])


def get_current_user(token: str):
    user_id = get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


@router.post("/")
async def create_tree(tree: TreeCreate, token: str = Header()):
    user_id = get_current_user(token)
    tree_id = await crud.create_tree(user_id, tree.name)
    return {"tree_id": tree_id}


@router.get("/")
async def get_trees(token: str = Header()):
    user_id = get_current_user(token)
    trees = await crud.get_user_trees(user_id)
    return trees