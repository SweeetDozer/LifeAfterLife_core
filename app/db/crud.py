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

crud = CRUD()