import os
import tempfile

import pytest

# Point the app at a throwaway SQLite DB *before* importing any app modules
# (app.config reads these env vars at import time).
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["RCLONE_REMOTE"] = ""

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DEFAULT_COLUMNS, Base, BoardColumn  # noqa: E402


@pytest.fixture
async def db():
    """Fresh schema + seeded columns for each test. Yields the session factory."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        for i, name in enumerate(DEFAULT_COLUMNS):
            session.add(BoardColumn(name=name, position=i))
        await session.commit()
    yield SessionLocal
    await engine.dispose()


@pytest.fixture
async def client(db):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
