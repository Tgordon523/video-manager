from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BoardColumn, Video


async def next_column_position(session: AsyncSession) -> int:
    max_pos = (await session.execute(select(func.max(BoardColumn.position)))).scalar()
    return (max_pos or 0) + 1


async def next_video_position(session: AsyncSession, column_id: int) -> int:
    max_pos = (
        await session.execute(
            select(func.max(Video.position)).where(Video.column_id == column_id)
        )
    ).scalar()
    return (max_pos or 0) + 1


async def renumber_column(
    session: AsyncSession,
    column_id: int,
    *,
    insert_video: Video | None = None,
    at: int = 0,
) -> None:
    """Renumber all videos in column_id. If insert_video is given, splice it at `at`."""
    exclude_id = insert_video.id if insert_video is not None else -1
    videos = list(
        (
            await session.execute(
                select(Video)
                .where(Video.column_id == column_id, Video.id != exclude_id)
                .order_by(Video.position, Video.id)
            )
        ).scalars()
    )
    if insert_video is not None:
        idx = max(0, min(at, len(videos)))
        videos.insert(idx, insert_video)
    for i, v in enumerate(videos):
        v.position = i
