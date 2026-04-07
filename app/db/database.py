import asyncpg

from app.core.config import settings


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        settings.validate_database()
        if self.pool is not None:
            return self.pool

        pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
        )
        self.pool = pool
        return self.pool

    async def disconnect(self):
        if self.pool is None:
            return

        pool, self.pool = self.pool, None
        await pool.close()


db = Database()
