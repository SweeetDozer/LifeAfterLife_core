from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in ROUTERS:
        application.include_router(router)

    return application


app = create_app()
