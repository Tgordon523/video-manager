from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import get_or_404
from ..models import Note, Video
from ..web import templates

router = APIRouter()


@router.post("/videos/{video_id}/notes")
async def add_note(
    video_id: int,
    request: Request,
    body: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    await get_or_404(session, Video, video_id)
    body = body.strip()
    if not body:
        return Response(status_code=204)
    note = Note(video_id=video_id, body=body)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return templates.TemplateResponse(request, "_note.html", {"note": note})


@router.get("/notes/{note_id}")
async def show_note(
    note_id: int, request: Request, session: AsyncSession = Depends(get_session)
):
    note = await get_or_404(session, Note, note_id)
    return templates.TemplateResponse(request, "_note.html", {"note": note})


@router.get("/notes/{note_id}/edit")
async def edit_note_form(
    note_id: int, request: Request, session: AsyncSession = Depends(get_session)
):
    note = await get_or_404(session, Note, note_id)
    return templates.TemplateResponse(request, "_note_edit.html", {"note": note})


@router.patch("/notes/{note_id}")
async def update_note(
    note_id: int,
    request: Request,
    body: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    note = await get_or_404(session, Note, note_id)
    note.body = body.strip() or note.body
    await session.commit()
    await session.refresh(note)
    return templates.TemplateResponse(request, "_note.html", {"note": note})


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, session: AsyncSession = Depends(get_session)):
    note = await session.get(Note, note_id)
    if note is not None:
        await session.delete(note)
        await session.commit()
    # Empty body + outerHTML swap removes the note element from the DOM.
    return Response(status_code=200)
