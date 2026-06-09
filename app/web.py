"""Shared templating: the Jinja environment, display filters, and board loader."""

from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import BoardColumn, Video

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_size(num: int | None) -> str:
    if not num:
        return ""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _register_filters() -> None:
    templates.env.filters["duration"] = format_duration
    templates.env.filters["filesize"] = format_size


_register_filters()


async def load_board(session: AsyncSession) -> list[BoardColumn]:
    """Load all columns with their videos and notes eagerly (async-safe)."""
    stmt = (
        select(BoardColumn)
        .order_by(BoardColumn.position, BoardColumn.id)
        .options(selectinload(BoardColumn.videos).selectinload(Video.notes))
    )
    return list((await session.execute(stmt)).scalars().all())
