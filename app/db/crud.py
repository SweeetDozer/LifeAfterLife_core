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

REFRESH_TOKEN_SELECT = """
SELECT
    id,
    user_id,
    family_id,
    token_id,
    token_hash,
    expires_at,
    created_at,
    last_used_at,
    revoked_at,
    replaced_by_token_id
FROM user_refresh_tokens
"""

AUTH_THROTTLE_SELECT = """
SELECT
    id,
    throttle_key_type,
    throttle_key_value,
    attempt_count,
    window_started_at,
    last_attempt_at,
    locked_until,
    created_at,
    updated_at
FROM auth_throttle_entries
"""

USER_PUBLIC_SELECT = """
SELECT
    id,
    email,
    created_at
FROM users
"""

TREE_ACCESS_SELECT = """
SELECT
    tree_access.user_id,
    users.email,
    tree_access.access_level::text AS access_level
FROM tree_access
JOIN users ON users.id = tree_access.user_id
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
    TREE_ACCESS_ROLE_BY_STORAGE = {
        "viewer": "viewer",
        "editor": "editor",
        "owner": "owner",
    }

    TREE_ACCESS_STORAGE_BY_ROLE = {
        "viewer": "viewer",
        "editor": "editor",
    }
    TREE_ACCESS_ASSIGNABLE_ROLES = frozenset({"viewer", "editor"})

    @staticmethod
    def _record_to_dict(record):
        return dict(record) if record else None

    @staticmethod
    def _records_to_list(records):
        return [dict(record) for record in records]

    @staticmethod
    def _executor(connection=None):
        return connection or db.pool

    @classmethod
    def _normalize_tree_access_level(cls, access_level: str | None):
        if access_level is None:
            return None
        return cls.TREE_ACCESS_ROLE_BY_STORAGE.get(access_level, access_level)

    @classmethod
    def _to_tree_access_storage(cls, access_level: str):
        normalized_access_level = cls.TREE_ACCESS_STORAGE_BY_ROLE.get(
            access_level,
            access_level,
        )
        if normalized_access_level not in cls.TREE_ACCESS_ASSIGNABLE_ROLES:
            raise ValueError(f"Unsupported tree access role: {access_level}")
        return normalized_access_level

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

    async def create_refresh_token(
        self,
        user_id: int,
        family_id: str,
        token_id: str,
        token_hash: str,
        expires_at,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        INSERT INTO user_refresh_tokens (user_id, family_id, token_id, token_hash, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """
        return await executor.fetchval(
            query,
            user_id,
            family_id,
            token_id,
            token_hash,
            expires_at,
        )

    async def get_refresh_token_by_token_id(
        self,
        token_id: str,
        connection=None,
        for_update: bool = False,
    ):
        executor = self._executor(connection)
        query = f"""
        {REFRESH_TOKEN_SELECT}
        WHERE token_id = $1
        """
        if for_update:
            query = f"{query}\nFOR UPDATE"
        record = await executor.fetchrow(query, token_id)
        return self._record_to_dict(record)

    async def rotate_refresh_token(
        self,
        current_token_row_id: int,
        next_token_id: str,
        next_token_hash: str,
        next_expires_at,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE user_refresh_tokens
        SET
            revoked_at = CURRENT_TIMESTAMP,
            last_used_at = CURRENT_TIMESTAMP,
            replaced_by_token_id = $2
        WHERE id = $1
        """
        await executor.execute(query, current_token_row_id, next_token_id)

        insert_query = """
        INSERT INTO user_refresh_tokens (user_id, family_id, token_id, token_hash, expires_at)
        SELECT user_id, family_id, $2, $3, $4
        FROM user_refresh_tokens
        WHERE id = $1
        RETURNING id
        """
        return await executor.fetchval(
            insert_query,
            current_token_row_id,
            next_token_id,
            next_token_hash,
            next_expires_at,
        )

    async def revoke_refresh_token_family(
        self,
        family_id: str,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE user_refresh_tokens
        SET
            revoked_at = CURRENT_TIMESTAMP
        WHERE family_id = $1
          AND revoked_at IS NULL
        """
        await executor.execute(query, family_id)

    async def revoke_refresh_token_family_for_user(
        self,
        user_id: int,
        family_id: str,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE user_refresh_tokens
        SET
            revoked_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
          AND family_id = $2
          AND revoked_at IS NULL
        """
        await executor.execute(query, user_id, family_id)

    async def revoke_all_refresh_tokens_for_user(
        self,
        user_id: int,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE user_refresh_tokens
        SET
            revoked_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
          AND revoked_at IS NULL
        """
        await executor.execute(query, user_id)

    async def get_auth_throttle_entry(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        connection=None,
        for_update: bool = False,
    ):
        executor = self._executor(connection)
        query = f"""
        {AUTH_THROTTLE_SELECT}
        WHERE throttle_key_type = $1
          AND throttle_key_value = $2
        """
        if for_update:
            query = f"{query}\nFOR UPDATE"
        record = await executor.fetchrow(query, throttle_key_type, throttle_key_value)
        return self._record_to_dict(record)

    async def create_auth_throttle_entry(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        attempt_count: int,
        window_started_at,
        last_attempt_at,
        locked_until,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        INSERT INTO auth_throttle_entries (
            throttle_key_type,
            throttle_key_value,
            attempt_count,
            window_started_at,
            last_attempt_at,
            locked_until
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """
        return await executor.fetchval(
            query,
            throttle_key_type,
            throttle_key_value,
            attempt_count,
            window_started_at,
            last_attempt_at,
            locked_until,
        )

    async def update_auth_throttle_entry(
        self,
        entry_id: int,
        attempt_count: int,
        window_started_at,
        last_attempt_at,
        locked_until,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE auth_throttle_entries
        SET
            attempt_count = $2,
            window_started_at = $3,
            last_attempt_at = $4,
            locked_until = $5,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """
        await executor.execute(
            query,
            entry_id,
            attempt_count,
            window_started_at,
            last_attempt_at,
            locked_until,
        )

    async def delete_auth_throttle_entry(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        DELETE FROM auth_throttle_entries
        WHERE throttle_key_type = $1
          AND throttle_key_value = $2
        """
        await executor.execute(query, throttle_key_type, throttle_key_value)

    async def upsert_tree_access(self, tree_id: int, user_id: int, access_level: str):
        stored_access_level = self._to_tree_access_storage(access_level)
        query = """
        INSERT INTO tree_access (tree_id, user_id, access_level)
        VALUES ($1, $2, $3)
        ON CONFLICT (tree_id, user_id)
        DO UPDATE SET access_level = EXCLUDED.access_level
        """
        await db.pool.execute(query, tree_id, user_id, stored_access_level)

    async def delete_tree_owner_access_entry(
        self,
        tree_id: int,
        owner_id: int | None,
        connection=None,
    ):
        if not owner_id:
            return False
        return await self.delete_tree_access(tree_id, owner_id, connection=connection)

    async def delete_tree_access(self, tree_id: int, user_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        DELETE FROM tree_access
        WHERE tree_id = $1 AND user_id = $2
        """
        result = await executor.execute(query, tree_id, user_id)
        return str(result).endswith("1")

    async def get_tree_access_entry(self, tree_id: int, user_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {TREE_ACCESS_SELECT}
        JOIN family_trees ON family_trees.id = tree_access.tree_id
        WHERE tree_access.tree_id = $1
          AND tree_access.user_id = $2
          AND family_trees.user_id <> tree_access.user_id
        """
        record = self._record_to_dict(await executor.fetchrow(query, tree_id, user_id))
        if record:
            record["access_level"] = self._normalize_tree_access_level(
                record.get("access_level")
            )
        return record

    async def get_tree_access_list(
        self,
        tree_id: int,
        owner: dict | None = None,
        connection=None,
    ):
        executor = self._executor(connection)
        query = f"""
        {TREE_ACCESS_SELECT}
        JOIN family_trees ON family_trees.id = tree_access.tree_id
        WHERE tree_access.tree_id = $1
          AND family_trees.user_id <> tree_access.user_id
        ORDER BY users.email
        """
        records = self._records_to_list(await executor.fetch(query, tree_id))
        for record in records:
            record["access_level"] = self._normalize_tree_access_level(
                record.get("access_level")
            )
        if owner and owner.get("owner_id"):
            owner_user = await self.get_user_by_id(owner["owner_id"])
            if owner_user:
                records.insert(
                    0,
                    {
                        "user_id": owner_user["id"],
                        "email": owner_user["email"],
                        "access_level": "owner",
                    },
                )
        return records

    async def count_tree_access_entries(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        SELECT COUNT(*)
        FROM tree_access
        JOIN family_trees ON family_trees.id = tree_access.tree_id
        WHERE tree_access.tree_id = $1
          AND family_trees.user_id <> tree_access.user_id
        """
        return int(await executor.fetchval(query, tree_id) or 0)

    async def get_tree_role(self, user_id: int, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        SELECT
            CASE
                WHEN family_trees.user_id = $1 THEN 'owner'
                WHEN tree_access.access_level IS NOT NULL THEN tree_access.access_level::text
                WHEN family_trees.is_public = TRUE THEN 'viewer'
                ELSE NULL
            END AS access_level
        FROM family_trees
        LEFT JOIN tree_access
            ON tree_access.tree_id = family_trees.id
            AND tree_access.user_id = $1
        WHERE family_trees.id = $2
        """
        return await executor.fetchval(query, user_id, tree_id)

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

    async def update_tree(
        self,
        tree_id: int,
        name: str,
        description: str | None,
        is_public: bool,
        connection=None,
    ):
        executor = self._executor(connection)
        query = """
        UPDATE family_trees
        SET name = $2, description = $3, is_public = $4
        WHERE id = $1
        """
        await executor.execute(query, tree_id, name, description, is_public)

    async def delete_tree(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        DELETE FROM family_trees
        WHERE id = $1
        """
        result = await executor.execute(query, tree_id)
        return str(result).endswith("1")

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
        result = self._records_to_list(records)
        for record in result:
            record["access_level"] = self._normalize_tree_access_level(
                record.get("access_level")
            )
        return result

    async def user_can_view_tree(self, user_id: int, tree_id: int, connection=None):
        return (await self.get_tree_role(user_id, tree_id, connection=connection)) is not None

    async def user_can_edit_tree(self, user_id: int, tree_id: int, connection=None):
        return await self.get_tree_role(
            user_id,
            tree_id,
            connection=connection,
        ) in {"owner", "editor"}

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

    async def update_person(
        self,
        person_id: int,
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
        UPDATE persons
        SET
            first_name = $2,
            midle_name = $3,
            last_name = $4,
            gender = $5,
            date_of_birth = $6,
            date_of_death = $7,
            photo_url = $8,
            info_about_person = $9
        WHERE id = $1
        """
        await executor.execute(
            query,
            person_id,
            first_name,
            middle_name,
            last_name,
            gender,
            birth_date,
            death_date,
            photo_url,
            description,
        )

    async def delete_person(self, person_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        DELETE FROM persons
        WHERE id = $1
        """
        result = await executor.execute(query, person_id)
        return str(result).endswith("1")

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

    async def count_tree_persons(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        SELECT COUNT(*)
        FROM persons
        WHERE tree_id = $1
        """
        return int(await executor.fetchval(query, tree_id) or 0)

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

    async def count_person_relationships(self, person_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        SELECT COUNT(*)
        FROM relationships
        WHERE from_person_id = $1 OR to_person_id = $1
        """
        return int(await executor.fetchval(query, person_id) or 0)

    async def get_tree_relationships(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {RELATIONSHIP_SELECT}
        WHERE tree_id = $1
        ORDER BY id
        """
        records = await executor.fetch(query, tree_id)
        return self._records_to_list(records)

    async def count_tree_relationships(self, tree_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        SELECT COUNT(*)
        FROM relationships
        WHERE tree_id = $1
        """
        return int(await executor.fetchval(query, tree_id) or 0)

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

    async def get_relationship(self, relationship_id: int, connection=None):
        executor = self._executor(connection)
        query = f"""
        {RELATIONSHIP_SELECT}
        WHERE id = $1
        """
        record = await executor.fetchrow(query, relationship_id)
        return self._record_to_dict(record)

    async def delete_relationship(self, relationship_id: int, connection=None):
        executor = self._executor(connection)
        query = """
        DELETE FROM relationships
        WHERE id = $1
        """
        result = await executor.execute(query, relationship_id)
        return str(result).endswith("1")

    async def delete_relationships(self, relationship_ids: list[int], connection=None):
        if not relationship_ids:
            return 0

        executor = self._executor(connection)
        query = """
        DELETE FROM relationships
        WHERE id = ANY($1::int[])
        """
        result = await executor.execute(query, relationship_ids)
        return int(str(result).split()[-1])


crud = CRUD()
