import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from account_hub.api.limiter import limiter
from account_hub.api.routers import accounts, auth, emails, oauth, search
from account_hub.db.base import engine

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    return app


app = create_app()
