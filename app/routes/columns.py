from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import BoardColumn, Video
from ..ordering import next_column_position
from ..web import load_board, templates

router = APIRouter()


async def _board_response(request: Request, session: AsyncSession):
    columns = await load_board(session)
    return templates.TemplateResponse(
        request, "_board.html", {"columns": columns}
    )


@router.post("/columns")
async def create_column(
    request: Request,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    name = name.strip()
    if name:
        pos = await next_column_position(session)
        session.add(BoardColumn(name=name, position=pos))
        await session.commit()
    return await _board_response(request, session)


@router.patch("/columns/{column_id}")
async def rename_column(
    column_id: int,
    request: Request,
    name: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    column = await session.get(BoardColumn, column_id)
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found")
    name = name.strip()
    if name:
        column.name = name
        await session.commit()
    return await _board_response(request, session)


@router.delete("/columns/{column_id}")
async def delete_column(
    column_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    column = await session.get(BoardColumn, column_id)
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found")
    count = (
        await session.execute(
            select(func.count(Video.id)).where(Video.column_id == column_id)
        )
    ).scalar()
    if count:
        raise HTTPException(
            status_code=400,
            detail="Move or remove the videos in this column before deleting it.",
        )
    await session.delete(column)
    await session.commit()
    return await _board_response(request, session)
