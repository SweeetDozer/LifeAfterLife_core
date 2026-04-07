import asyncpg

from app.core.config import settings


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
        )

    async def disconnect(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None


db = Database()
