from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_id
from app.models.kinship import KinshipResponse
from app.services.graph_service import graph_service
from app.services.kinship_service import kinship_service
from app.services.permissions import ensure_tree_persons_access

router = APIRouter(prefix="/kinship", tags=["kinship"])
TreeIdQuery = Annotated[int, Query(gt=0)]
PersonIdQuery = Annotated[int, Query(gt=0)]


@router.get("/", response_model=KinshipResponse)
async def get_kinship(
    tree_id: TreeIdQuery,
    from_person_id: PersonIdQuery,
    to_person_id: PersonIdQuery,
    user_id: int = Depends(get_current_user_id),
):
    await ensure_tree_persons_access(
        user_id,
        tree_id,
        [from_person_id, to_person_id],
        access="view",
    )

    path_details = await graph_service.find_path_details(
        tree_id,
        from_person_id,
        to_person_id,
    )
    if not path_details:
        raise HTTPException(status_code=404, detail="No path")

    path = path_details["path"]
    relations = await kinship_service.path_to_relations(
        tree_id,
        path_details["steps"],
    )
    result = await kinship_service.interpret(tree_id, relations, to_person_id)
    line = await kinship_service.detect_line(tree_id, relations)
    lca = await graph_service.find_lca(tree_id, from_person_id, to_person_id)

    return KinshipResponse(
        path=path,
        relations=relations,
        result=result,
        line=line,
        lca=lca,
    )
