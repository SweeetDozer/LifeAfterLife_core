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
    
    async def create_tree(self, owner_id: int, name: str):
        query = """
        INSERT INTO family_trees (owner_id, name)
        VALUES ($1, $2)
        RETURNING id
        """
        return await db.pool.fetchval(query, owner_id, name)


    async def get_user_trees(self, user_id: int):
        query = """
        SELECT * FROM family_trees
        WHERE owner_id = $1
        """
        return await db.pool.fetch(query, user_id)






crud = CRUD()
