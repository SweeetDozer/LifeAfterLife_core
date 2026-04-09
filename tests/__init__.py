import sys
import types


if "asyncpg" not in sys.modules:
    asyncpg = types.ModuleType("asyncpg")

    class PostgresError(Exception):
        pass

    async def create_pool(*args, **kwargs):
        raise RuntimeError("asyncpg.create_pool should not be used in unit tests")

    asyncpg.create_pool = create_pool
    asyncpg.PostgresError = PostgresError
    sys.modules["asyncpg"] = asyncpg


if "dotenv" not in sys.modules:
    dotenv = types.ModuleType("dotenv")

    def load_dotenv(*args, **kwargs):
        return False

    dotenv.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv
