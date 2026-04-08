from fastapi import HTTPException

from app.db.crud import crud
from app.services.permissions import ensure_tree_owner_access


class TreeAccessService:
    async def list_access(self, actor_user_id: int, tree_id: int):
        tree = await ensure_tree_owner_access(actor_user_id, tree_id)
        return await crud.get_tree_access_list(tree_id, owner=tree)

    async def grant_access(
        self,
        actor_user_id: int,
        tree_id: int,
        target_email: str,
        access_level: str,
    ):
        tree = await ensure_tree_owner_access(actor_user_id, tree_id)
        user = await crud.get_user_by_email(target_email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user["id"] == tree.get("owner_id"):
            raise HTTPException(
                status_code=400,
                detail="Owner already has full access",
            )

        await crud.upsert_tree_access(tree_id, user["id"], access_level)
        return {
            "user_id": user["id"],
            "access_level": access_level,
        }

    async def revoke_access(self, actor_user_id: int, tree_id: int, target_user_id: int):
        tree = await ensure_tree_owner_access(actor_user_id, tree_id)
        if target_user_id == tree.get("owner_id"):
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke owner access",
            )

        deleted = await crud.delete_tree_access(tree_id, target_user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Access entry not found")

        return {"detail": "Access revoked"}


tree_access_service = TreeAccessService()
