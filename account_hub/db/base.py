import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from account_hub.config import settings

logger = logging.getLogger("account_hub")


def _build_engine():
    url = settings.database_url
    # Log a redacted version so we can debug connection issues
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        redacted = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}{parsed.path}"
        logger.info("DATABASE_URL: %s", redacted)
    except Exception:
        logger.warning("DATABASE_URL does not look like a valid URL (length=%d)", len(url))
    return create_async_engine(url, echo=False)


engine = _build_engine()

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
