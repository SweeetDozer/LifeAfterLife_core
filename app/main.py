from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.db.database import db
from app.routes import ROUTERS


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    try:
        await db.connect()
        yield
    finally:
        await db.disconnect()


def create_app() -> FastAPI:
    application = FastAPI(lifespan=lifespan)

    for router in ROUTERS:
        application.include_router(router)

    return application


app = create_app()
