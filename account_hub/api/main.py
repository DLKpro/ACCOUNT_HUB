from contextlib import asynccontextmanager

from fastapi import FastAPI

from account_hub.api.routers import auth, emails, oauth, search
from account_hub.db.base import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register OAuth providers on startup
    from account_hub.oauth.google import setup_google
    from account_hub.oauth.microsoft import setup_microsoft
    from account_hub.oauth.apple import setup_apple
    from account_hub.oauth.meta import setup_meta

    setup_google()
    setup_microsoft()
    setup_apple()
    setup_meta()

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
    app.include_router(oauth.router)
    app.include_router(search.router)
    return app


app = create_app()
