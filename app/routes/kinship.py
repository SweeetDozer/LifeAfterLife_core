from fastapi import APIRouter, HTTPException, Header
from app.services.graph_service import graph_service
from app.services.kinship_service import kinship_service
from app.core.security import get_user_by_token

router = APIRouter(prefix="/kinship", tags=["kinship"])


def get_current_user(token: str):
    user_id = get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


@router.get("/")
async def get_kinship(
    tree_id: int,
    from_person_id: int,
    to_person_id: int,
    token: str = Header()
):
    user_id = get_current_user(token)

    path = await graph_service.find_path(
        tree_id,
        from_person_id,
        to_person_id
    )

    if not path:
        raise HTTPException(status_code=404, detail="No path")

    relations = await kinship_service.path_to_relations(path)
    result = kinship_service.interpret(relations)

    return {
        "path": path,
        "relations": relations,
        "result": result
    }