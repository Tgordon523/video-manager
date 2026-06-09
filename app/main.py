import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from . import scanner
from .db import SessionLocal
from .models import DEFAULT_COLUMNS, BoardColumn
from .routes import board, columns, notes, videos
from .web import BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("video_manager")


async def seed_columns() -> None:
    async with SessionLocal() as session:
        count = (await session.execute(select(func.count(BoardColumn.id)))).scalar()
        if count:
            return
        for i, name in enumerate(DEFAULT_COLUMNS):
            session.add(BoardColumn(name=name, position=i))
        await session.commit()
        logger.info("Seeded default columns: %s", ", ".join(DEFAULT_COLUMNS))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_columns()
    # Held by reference for the lifetime of the app so they are not GC'd.
    tasks = [asyncio.create_task(coro) for coro in scanner.background_tasks()]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Video Manager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(board.router)
app.include_router(videos.router)
app.include_router(notes.router)
app.include_router(columns.router)
