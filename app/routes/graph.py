from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user_id
from app.models.graph import GraphPathResponse
from app.services.graph_service import graph_service
from app.services.permissions import ensure_tree_persons_access

router = APIRouter(prefix="/graph", tags=["graph"])
TreeIdQuery = Annotated[int, Query(gt=0)]
PersonIdQuery = Annotated[int, Query(gt=0)]


@router.get("/path", response_model=GraphPathResponse)
async def find_path(
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

    path = await graph_service.find_path(tree_id, from_person_id, to_person_id)

    if not path:
        raise HTTPException(status_code=404, detail="No path found")

    return GraphPathResponse(path=path)
