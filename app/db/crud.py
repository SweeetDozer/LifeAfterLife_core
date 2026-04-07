from app.db.database import db


TREE_SELECT = """
SELECT
    id,
    user_id AS owner_id,
    name,
    description,
    is_public,
    created_at
FROM family_trees
"""

PERSON_SELECT = """
SELECT
    id,
    tree_id,
    first_name,
    midle_name AS middle_name,
    last_name,
    date_of_birth AS birth_date,
    date_of_death AS death_date,
    gender,
    photo_url,
    info_about_person AS description
FROM persons
"""


class CRUD:

    @staticmethod
    def _record_to_dict(record):
        return dict(record) if record else None

    @staticmethod
    def _records_to_list(records):
        return [dict(record) for record in records]

    async def create_user(self, email: str, password_hash: str):
        query = """
        INSERT INTO users (email, password_hash)
        VALUES ($1, $2)
        RETURNING id
        """
        return await db.pool.fetchval(query, email, password_hash)

    async def update_user_password_hash(self, user_id: int, password_hash: str):
        query = """
        UPDATE users
        SET password_hash = $2
        WHERE id = $1
        """
        await db.pool.execute(query, user_id, password_hash)

    async def get_user_by_email(self, email: str):
        query = "SELECT * FROM users WHERE email = $1"
        record = await db.pool.fetchrow(query, email)
        return self._record_to_dict(record)

    async def create_tree(
        self,
        owner_id: int,
        name: str,
        description: str | None = None,
        is_public: bool = False,
    ):
        query = """
        INSERT INTO family_trees (user_id, name, description, is_public)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """
        return await db.pool.fetchval(query, owner_id, name, description, is_public)

    async def get_tree(self, tree_id: int):
        query = f"""
        {TREE_SELECT}
        WHERE id = $1
        """
        record = await db.pool.fetchrow(query, tree_id)
        return self._record_to_dict(record)

    async def get_user_trees(self, user_id: int):
        query = """
        SELECT DISTINCT
            family_trees.id,
            family_trees.user_id AS owner_id,
            family_trees.name,
            family_trees.description,
            family_trees.is_public,
            family_trees.created_at,
            CASE
                WHEN family_trees.user_id = $1 THEN 'owner'
                ELSE tree_access.access_level::text
            END AS access_level
        FROM family_trees
        LEFT JOIN tree_access
            ON tree_access.tree_id = family_trees.id
            AND tree_access.user_id = $1
        WHERE family_trees.user_id = $1 OR tree_access.user_id = $1
        ORDER BY family_trees.created_at DESC
        """
        records = await db.pool.fetch(query, user_id)
        return self._records_to_list(records)

    async def user_can_view_tree(self, user_id: int, tree_id: int):
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM family_trees
            LEFT JOIN tree_access
                ON tree_access.tree_id = family_trees.id
                AND tree_access.user_id = $1
            WHERE family_trees.id = $2
              AND (
                    family_trees.user_id = $1
                    OR family_trees.is_public = TRUE
                    OR tree_access.user_id IS NOT NULL
              )
        )
        """
        return await db.pool.fetchval(query, user_id, tree_id)

    async def user_can_edit_tree(self, user_id: int, tree_id: int):
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM family_trees
            LEFT JOIN tree_access
                ON tree_access.tree_id = family_trees.id
                AND tree_access.user_id = $1
            WHERE family_trees.id = $2
              AND (
                    family_trees.user_id = $1
                    OR tree_access.access_level = 'edit'
              )
        )
        """
        return await db.pool.fetchval(query, user_id, tree_id)

    async def create_person(
        self,
        tree_id: int,
        first_name: str,
        middle_name: str | None = None,
        last_name: str | None = None,
        gender: str | None = None,
        birth_date=None,
        death_date=None,
        description: str | None = None,
        photo_url: str | None = None,
    ):
        query = """
        INSERT INTO persons (
            tree_id,
            first_name,
            midle_name,
            last_name,
            gender,
            date_of_birth,
            date_of_death,
            photo_url,
            info_about_person
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """
        return await db.pool.fetchval(
            query,
            tree_id,
            first_name,
            middle_name,
            last_name,
            gender,
            birth_date,
            death_date,
            photo_url,
            description,
        )

    async def get_person(self, person_id: int):
        query = f"""
        {PERSON_SELECT}
        WHERE id = $1
        """
        record = await db.pool.fetchrow(query, person_id)
        return self._record_to_dict(record)

    async def get_tree_persons(self, tree_id: int):
        query = f"""
        {PERSON_SELECT}
        WHERE tree_id = $1
        ORDER BY first_name, last_name, id
        """
        records = await db.pool.fetch(query, tree_id)
        return self._records_to_list(records)

    async def create_relationship(
        self,
        tree_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
    ):
        query = """
        INSERT INTO relationships (
            tree_id,
            from_person_id,
            to_person_id,
            relationship_type
        )
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (from_person_id, to_person_id, relationship_type) DO NOTHING
        RETURNING id
        """
        return await db.pool.fetchval(
            query,
            tree_id,
            from_person_id,
            to_person_id,
            relationship_type,
        )

    async def get_person_relationships(self, person_id: int):
        query = """
        SELECT *
        FROM relationships
        WHERE from_person_id = $1
        """
        records = await db.pool.fetch(query, person_id)
        return self._records_to_list(records)

    async def get_tree_relationships(self, tree_id: int):
        query = """
        SELECT id, tree_id, from_person_id, to_person_id, relationship_type
        FROM relationships
        WHERE tree_id = $1
        """
        records = await db.pool.fetch(query, tree_id)
        return self._records_to_list(records)

    async def get_relationship(self, from_id: int, to_id: int):
        query = """
        SELECT relationship_type
        FROM relationships
        WHERE from_person_id = $1 AND to_person_id = $2
        """
        record = await db.pool.fetchrow(query, from_id, to_id)
        return self._record_to_dict(record)


crud = CRUD()
