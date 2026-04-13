from contextlib import asynccontextmanager

from fastapi import FastAPI

from account_hub.api.routers import auth, emails
from account_hub.db.base import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Account Hub",
        description="Identity aggregation API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(auth.router)
    app.include_router(emails.router)
    return app


app = create_app()
