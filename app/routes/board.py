from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..scanner import ScanCoordinator, get_coordinator
from ..web import load_board, templates

router = APIRouter()


@router.get("/")
async def board(request: Request, session: AsyncSession = Depends(get_session)):
    columns = await load_board(session)
    return templates.TemplateResponse(
        request,
        "board.html",
        {"columns": columns, "settings": settings},
    )


@router.post("/scan")
async def scan_now(
    request: Request,
    session: AsyncSession = Depends(get_session),
    coord: ScanCoordinator = Depends(get_coordinator),
):
    """Discover new files now (fast). The download worker picks them up."""
    await coord.discover()
    columns = await load_board(session)
    return templates.TemplateResponse(
        request,
        "_board.html",
        {"columns": columns},
    )
