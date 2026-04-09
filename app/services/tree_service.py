from app.db.crud import crud
from app.db.database import db
from app.models.tree import TreeUpdate
from app.services.permissions import ensure_tree_delete_access, ensure_tree_edit_access


class TreeService:
    async def update_tree(self, user_id: int, tree_id: int, tree_update: TreeUpdate):
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                current_tree = await ensure_tree_edit_access(
                    user_id,
                    tree_id,
                    connection=connection,
                )
                patch_data = tree_update.model_dump(exclude_unset=True)
                merged_tree = {
                    "name": current_tree["name"],
                    "description": current_tree["description"],
                    "is_public": current_tree["is_public"],
                }
                merged_tree.update(patch_data)
                await crud.update_tree(
                    tree_id,
                    merged_tree["name"],
                    merged_tree["description"],
                    merged_tree["is_public"],
                    connection=connection,
                )

        return {
            "id": current_tree["id"],
            "owner_id": current_tree["owner_id"],
            "name": merged_tree["name"],
            "description": merged_tree["description"],
            "is_public": merged_tree["is_public"],
            "created_at": current_tree["created_at"],
            "access_level": "owner"
            if current_tree["owner_id"] == user_id
            else "editor",
        }

    async def delete_tree(self, user_id: int, tree_id: int):
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                await ensure_tree_delete_access(user_id, tree_id, connection=connection)
                # We count dependent rows explicitly inside the same transaction,
                # then delete only the root tree row in code. Persons,
                # relationships, and delegated access rows are physically removed
                # by FK ON DELETE CASCADE in Postgres.
                deleted_persons = await crud.count_tree_persons(
                    tree_id,
                    connection=connection,
                )
                deleted_relationships = await crud.count_tree_relationships(
                    tree_id,
                    connection=connection,
                )
                deleted_access_entries = await crud.count_tree_access_entries(
                    tree_id,
                    connection=connection,
                )
                deleted = await crud.delete_tree(tree_id, connection=connection)

        if not deleted:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Tree not found")

        return {
            "detail": "Tree deleted",
            "deleted_persons": deleted_persons,
            "deleted_relationships": deleted_relationships,
            "deleted_access_entries": deleted_access_entries,
        }


tree_service = TreeService()
