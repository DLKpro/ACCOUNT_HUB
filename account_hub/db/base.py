import sys
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from account_hub.config import settings

url = settings.database_url
# Print redacted URL to stderr so Railway logs show what value we're actually getting
print(f"[DB] DATABASE_URL scheme={url.split('://')[0] if '://' in url else 'MISSING'} length={len(url)} first_20={url[:20]!r}", file=sys.stderr, flush=True)

engine = create_async_engine(url, echo=False)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
