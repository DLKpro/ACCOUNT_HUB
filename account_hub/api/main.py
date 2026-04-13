import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from account_hub.api.limiter import limiter
from account_hub.api.routers import accounts, auth, emails, oauth, search
from account_hub.db.base import Base, engine

logger = logging.getLogger("account_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Account Hub API starting")

    # Auto-create tables if they don't exist
    from account_hub.db import models  # noqa: F401
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured")
    except Exception:
        logger.exception("Failed to connect to database — app will start but DB operations will fail")

    # Register OAuth providers on startup
    from account_hub.oauth.apple import setup_apple
    from account_hub.oauth.google import setup_google
    from account_hub.oauth.meta import setup_meta
    from account_hub.oauth.microsoft import setup_microsoft

    setup_google()
    setup_microsoft()
    setup_apple()
    setup_meta()
    logger.info("OAuth providers registered")

    yield

    logger.info("Account Hub API shutting down")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Account Hub",
        description="Identity aggregation API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    from account_hub.config import settings
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if settings.app_url:
        origins.append(settings.app_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Security headers + request logging middleware
    @app.middleware("http")
    async def security_and_logging(request: Request, call_next):
        logger.info("%s %s", request.method, request.url.path)
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    app.include_router(auth.router)
    app.include_router(emails.router)
    app.include_router(oauth.router)
    app.include_router(search.router)
    app.include_router(accounts.router)

    # Serve frontend static files in production
    static_dir = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if static_dir.is_dir():
        from fastapi.responses import FileResponse

        # Serve static assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="static-assets")

        # Serve other static files (favicon, etc.)
        @app.get("/favicon.svg")
        async def favicon():
            return FileResponse(static_dir / "favicon.svg")

        # SPA fallback: serve index.html for all non-API routes
        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
