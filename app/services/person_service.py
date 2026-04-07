from asyncpg import PostgresError

from app.db.crud import crud
from app.db.database import db
from app.models.person import PersonCreate
from app.services.permissions import (
    ensure_person_view_access,
    ensure_tree_edit_access,
    ensure_tree_view_access,
)


class PersonServiceError(Exception):
    pass


class PersonService:

    async def create_person(self, user_id: int, person: PersonCreate) -> int:
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                await ensure_tree_edit_access(
                    user_id,
                    person.tree_id,
                    connection=connection,
                )

                try:
                    person_id = await crud.create_person(
                        **person.model_dump(),
                        connection=connection,
                    )
                except PostgresError as exc:
                    raise PersonServiceError("Failed to create person") from exc

        if person_id is None:
            raise PersonServiceError("Failed to create person")

        return person_id

    async def get_tree_persons(self, user_id: int, tree_id: int):
        await ensure_tree_view_access(user_id, tree_id)
        return await crud.get_tree_persons(tree_id)

    async def get_person(self, user_id: int, person_id: int):
        return await ensure_person_view_access(user_id, person_id)


person_service = PersonService()
