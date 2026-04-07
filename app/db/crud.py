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

USER_AUTH_SELECT = """
SELECT
    id,
    email,
    password_hash,
    created_at
FROM users
"""

USER_PUBLIC_SELECT = """
SELECT
    id,
    email,
    created_at
FROM users
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

RELATIONSHIP_SELECT = """
SELECT
    id,
    tree_id,
    from_person_id,
    to_person_id,
    relationship_type::text AS relationship_type
FROM relationships
"""


class CRUD:

    @staticmethod
    def _record_to_dict(record):
        return dict(record) if record else None

    @staticmethod
    def _records_to_list(records):
        return [dict(record) for record in records]

    @staticmethod
    def _executor(connection=None):
        return connection or db.pool

    async def create_user(self, email: str, password_hash: str):
        normalized_email = email.strip().lower()

        async with db.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1)::bigint)",
                    normalized_email,
                )

                existing = await connection.fetchrow(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(email) = LOWER($1)
                    ORDER BY id
                    LIMIT 1
                    """,
                    normalized_email,
                )
                if existing:
                    return None

                query = """
                INSERT INTO users (email, password_hash)
                VALUES ($1, $2)
                RETURNING id
                """
                return await connection.fetchval(query, normalized_email, password_hash)

    async def update_user_password_hash(self, user_id: int, password_hash: str):
        query = """
        UPDATE users
        SET password_hash = $2
        WHERE id = $1
        """
        await db.pool.execute(query, user_id, password_hash)

    async def get_user_by_email(self, email: str):
        normalized_email = email.strip().lower()
        query = f"""
        {USER_AUTH_SELECT}
        WHERE LOWER(email) = LOWER($1)
        ORDER BY id
        LIMIT 1
        """
        record = await db.pool.fetchrow(query, normalized_email)
        return self._record_to_dict(record)

    async def get_user_by_id(self, user_id: int):
        query = f"""
        {USER_PUBLIC_SELECT}
        WHERE id = $1
        """
        record = await db.pool.fetchrow(query, user_id)
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

    async def get_tree(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {TREE_SELECT}
        WHERE id = $1
        """
        record = await executor.fetchrow(query, tree_id)
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

    async def user_can_view_tree(self, user_id: int, tree_id: int, connection=None):
        executor = self._executor(connection)
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
        return await executor.fetchval(query, user_id, tree_id)

    async def user_can_edit_tree(self, user_id: int, tree_id: int, connection=None):
        executor = self._executor(connection)
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
        return await executor.fetchval(query, user_id, tree_id)

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
        connection=None,
    ):
        executor = self._executor(connection)
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
        return await executor.fetchval(
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

    async def get_person(self, person_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {PERSON_SELECT}
        WHERE id = $1
        """
        record = await executor.fetchrow(query, person_id)
        return self._record_to_dict(record)

    async def get_tree_person(self, tree_id: int, person_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {PERSON_SELECT}
        WHERE tree_id = $1 AND id = $2
        """
        record = await executor.fetchrow(query, tree_id, person_id)
        return self._record_to_dict(record)

    async def get_tree_persons(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {PERSON_SELECT}
        WHERE tree_id = $1
        ORDER BY first_name, last_name, id
        """
        records = await executor.fetch(query, tree_id)
        return self._records_to_list(records)

    async def create_relationship(
        self,
        tree_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        connection=None,
    ):
        executor = self._executor(connection)
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
        return await executor.fetchval(
            query,
            tree_id,
            from_person_id,
            to_person_id,
            relationship_type,
        )

    async def get_person_relationships(self, person_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {RELATIONSHIP_SELECT}
        WHERE from_person_id = $1 OR to_person_id = $1
        ORDER BY id
        """
        records = await executor.fetch(query, person_id)
        return self._records_to_list(records)

    async def get_tree_relationships(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {RELATIONSHIP_SELECT}
        WHERE tree_id = $1
        ORDER BY id
        """
        records = await executor.fetch(query, tree_id)
        return self._records_to_list(records)

    async def get_ordered_relationship_types(
        self,
        from_id: int,
        to_id: int,
        tree_id: int | None = None,
        connection=None,
    ):
        executor = self._executor(connection)
        if tree_id is None:
            query = """
            SELECT DISTINCT relationship_type::text AS relationship_type
            FROM relationships
            WHERE from_person_id = $1 AND to_person_id = $2
            ORDER BY relationship_type::text
            """
            records = await executor.fetch(query, from_id, to_id)
        else:
            query = """
            SELECT DISTINCT relationship_type::text AS relationship_type
            FROM relationships
            WHERE tree_id = $1
              AND from_person_id = $2
              AND to_person_id = $3
            ORDER BY relationship_type::text
            """
            records = await executor.fetch(query, tree_id, from_id, to_id)
        return self._records_to_list(records)

    async def get_pair_relationships(
        self,
        first_person_id: int,
        second_person_id: int,
        tree_id: int | None = None,
        connection=None,
    ):
        executor = self._executor(connection)
        if tree_id is None:
            query = f"""
            {RELATIONSHIP_SELECT}
            WHERE (from_person_id = $1 AND to_person_id = $2)
               OR (from_person_id = $2 AND to_person_id = $1)
            ORDER BY id
            """
            records = await executor.fetch(query, first_person_id, second_person_id)
        else:
            query = f"""
            {RELATIONSHIP_SELECT}
            WHERE tree_id = $1
              AND (
                    (from_person_id = $2 AND to_person_id = $3)
                    OR (from_person_id = $3 AND to_person_id = $2)
              )
            ORDER BY id
            """
            records = await executor.fetch(
                query,
                tree_id,
                first_person_id,
                second_person_id,
            )
        return self._records_to_list(records)


crud = CRUD()
