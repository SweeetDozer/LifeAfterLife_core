from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.services.graph_service import graph_service
from app.services.kinship_service import kinship_service
from app.services.permissions import ensure_person_view_access, ensure_tree_view_access

router = APIRouter(prefix="/kinship", tags=["kinship"])


@router.get("/")
async def get_kinship(
    tree_id: int,
    from_person_id: int,
    to_person_id: int,
    user_id: int = Depends(get_current_user_id),
):
    await ensure_tree_view_access(user_id, tree_id)
    from_person = await ensure_person_view_access(user_id, from_person_id)
    to_person = await ensure_person_view_access(user_id, to_person_id)

    if from_person["tree_id"] != tree_id or to_person["tree_id"] != tree_id:
        raise HTTPException(status_code=400, detail="Persons must belong to the requested tree")

    path = await graph_service.find_path(tree_id, from_person_id, to_person_id)
    if not path:
        raise HTTPException(status_code=404, detail="No path")

    relations = await kinship_service.path_to_relations(path)
    result = await kinship_service.interpret(relations, to_person_id)
    line = await kinship_service.detect_line(relations)
    lca = await graph_service.find_lca(tree_id, from_person_id, to_person_id)

    return {
        "path": path,
        "relations": relations,
        "result": result,
        "line": line,
        "lca": lca,
    }
