import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_session
from ..models import BoardColumn, Video
from ..ordering import renumber_column
from ..web import templates

router = APIRouter()


async def _get_video(session: AsyncSession, video_id: int) -> Video:
    video = (
        await session.execute(
            select(Video)
            .where(Video.id == video_id)
            .options(selectinload(Video.notes), selectinload(Video.column))
        )
    ).scalar_one_or_none()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/videos/{video_id}/move")
async def move_video(
    video_id: int,
    column_id: int = Form(...),
    position: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    video = await session.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    target = await session.get(BoardColumn, column_id)
    if target is None:
        raise HTTPException(status_code=400, detail="Unknown column")

    old_column_id = video.column_id
    video.column_id = column_id

    await renumber_column(session, column_id, insert_video=video, at=position)

    if old_column_id != column_id:
        await renumber_column(session, old_column_id)

    await session.commit()
    return Response(status_code=204)


@router.get("/videos/{video_id}")
async def video_detail(
    video_id: int, request: Request, session: AsyncSession = Depends(get_session)
):
    video = await _get_video(session, video_id)
    return templates.TemplateResponse(
        request, "video_detail.html", {"video": video}
    )


@router.get("/videos/{video_id}/card")
async def video_card(
    video_id: int, request: Request, session: AsyncSession = Depends(get_session)
):
    """Single-card fragment; pending/downloading cards poll this to self-update."""
    video = await _get_video(session, video_id)
    return templates.TemplateResponse(
        request, "_card.html", {"video": video}
    )


@router.get("/media/{video_id}")
async def media(video_id: int, session: AsyncSession = Depends(get_session)):
    video = await session.get(Video, video_id)
    if video is None or not video.local_path or not os.path.exists(video.local_path):
        raise HTTPException(status_code=404, detail="File not available")
    # FileResponse supports HTTP Range requests, so the browser can seek.
    return FileResponse(video.local_path, media_type="video/mp4", filename=video.name)


@router.get("/thumbnails/{video_id}")
async def thumbnail(video_id: int, session: AsyncSession = Depends(get_session)):
    video = await session.get(Video, video_id)
    if (
        video is None
        or not video.thumbnail_path
        or not os.path.exists(video.thumbnail_path)
    ):
        raise HTTPException(status_code=404, detail="No thumbnail")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")
