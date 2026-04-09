from asyncpg import PostgresError

from app.db.crud import crud
from app.db.database import db
from app.models.person import PersonCreate, PersonUpdate
from app.services.permissions import (
    ensure_person_edit_access,
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

    async def update_person(self, user_id: int, person_id: int, person_update: PersonUpdate):
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                current_person = await ensure_person_edit_access(
                    user_id,
                    person_id,
                    connection=connection,
                )
                patch_data = person_update.model_dump(exclude_unset=True)
                merged_person = {
                    "first_name": current_person["first_name"],
                    "middle_name": current_person["middle_name"],
                    "last_name": current_person["last_name"],
                    "birth_date": current_person["birth_date"],
                    "death_date": current_person["death_date"],
                    "description": current_person["description"],
                    "photo_url": current_person["photo_url"],
                    "gender": current_person["gender"],
                }
                merged_person.update(patch_data)

                try:
                    await crud.update_person(
                        person_id=person_id,
                        **merged_person,
                        connection=connection,
                    )
                except PostgresError as exc:
                    raise PersonServiceError("Failed to update person") from exc

        return await crud.get_person(person_id)

    async def delete_person(self, user_id: int, person_id: int):
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                await ensure_person_edit_access(
                    user_id,
                    person_id,
                    connection=connection,
                )
                # We only delete the person row in Python. Related relationship
                # rows are removed by Postgres via FK ON DELETE CASCADE, so the
                # API reports the number of dependent rows that the database is
                # going to delete as part of the same transaction.
                deleted_relationships = await crud.count_person_relationships(
                    person_id,
                    connection=connection,
                )
                deleted = await crud.delete_person(person_id, connection=connection)

        if not deleted:
            raise PersonServiceError("Failed to delete person")

        return {
            "detail": "Person deleted; related relationships removed by database cascade",
            "deleted_relationships": deleted_relationships,
        }


person_service = PersonService()
