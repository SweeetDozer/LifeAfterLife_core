from os import name

from app.db.database import db

class CRUD:

    async def create_user(self, email: str, password_hash: str):
        query = """
        INSERT INTO users (email, password_hash)
        VALUES ($1, $2)
        RETURNING id
        """
        return await db.pool.fetchval(query, email, password_hash)

    async def get_user_by_email(self, email: str):
        query = "SELECT * FROM users WHERE email = $1"
        return await db.pool.fetchrow(query, email)
 # ================================================================================================================
    async def create_tree(self, owner_id: int, name: str):
        query = """
        INSERT INTO family_trees (owner_id, name)
        VALUES ($1, $2)
        RETURNING id
        """
        return await db.pool.fetchval(query, owner_id, name)
# ================================================================================================================
    async def get_user_trees(self, user_id: int):
        query = """
        SELECT * FROM family_trees
        WHERE owner_id = $1
        """
        return await db.pool.fetch(query, user_id)
# ===============================================================================================================
    async def create_person(
        self,
        tree_id: int,
        first_name: str,
        middle_name: str,
        last_name: str,
        birth_date,
        death_date,
        description
    ):
        query = """
        INSERT INTO persons (
            tree_id, first_name, middle_name, last_name,
            birth_date, death_date, description
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """
        return await db.pool.fetchval(
            query,
            tree_id,
            first_name,
            middle_name,
            last_name,
            birth_date,
            death_date,
            description
        )

    async def get_person(self, person_id: int):
        query = "SELECT * FROM persons WHERE id = $1"
        return await db.pool.fetchrow(query, person_id)


    async def get_tree_persons(self, tree_id: int):
        query = "SELECT * FROM persons WHERE tree_id = $1"
        return await db.pool.fetch(query, tree_id)
# ================================================================================================================  
    async def create_relationship(
        self,
        tree_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str
    ):
        query = """
        INSERT INTO relationships (
            tree_id,
            from_person_id,
            to_person_id,
            relationship_type
        )
        VALUES ($1, $2, $3, $4)
        """
        await db.pool.execute(
            query,
            tree_id,
            from_person_id,
            to_person_id,
            relationship_type
        )


    async def get_person_relationships(self, person_id: int):
        query = """
        SELECT * FROM relationships
        WHERE from_person_id = $1
        """
        return await db.pool.fetch(query, person_id)

# ================================================================================================================
    async def get_tree_relationships(self, tree_id: int):
        query = """
        SELECT from_person_id, to_person_id, relationship_type
        FROM relationships
        WHERE tree_id = $1
        """
        return await db.pool.fetch(query, tree_id)

    async def get_relationship(self, from_id: int, to_id: int):
        query = """
        SELECT relationship_type
        FROM relationships
        WHERE from_person_id = $1 AND to_person_id = $2
        """
        return await db.pool.fetchrow(query, from_id, to_id)



crud = CRUD()
