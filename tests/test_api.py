from sqlalchemy import select

from app.models import BoardColumn, Note, Video


async def _columns(session):
    return (
        await session.execute(select(BoardColumn).order_by(BoardColumn.position))
    ).scalars().all()


async def test_board_renders(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Backlog" in resp.text
    assert "Published" in resp.text


async def test_move_video_changes_column_and_renumbers(client, db):
    async with db() as session:
        cols = await _columns(session)
        backlog, editing = cols[0], cols[1]
        v1 = Video(drive_file_id="v1", name="v1.mp4", column_id=backlog.id,
                   position=0, download_status="downloaded")
        v2 = Video(drive_file_id="v2", name="v2.mp4", column_id=backlog.id,
                   position=1, download_status="downloaded")
        session.add_all([v1, v2])
        await session.commit()
        v1_id, v2_id, editing_id, backlog_id = v1.id, v2.id, editing.id, backlog.id

    resp = await client.post(
        f"/videos/{v1_id}/move", data={"column_id": editing_id, "position": 0}
    )
    assert resp.status_code == 204

    async with db() as session:
        v1 = await session.get(Video, v1_id)
        v2 = await session.get(Video, v2_id)
        assert v1.column_id == editing_id and v1.position == 0
        # The remaining backlog card is renumbered from 1 down to 0.
        assert v2.column_id == backlog_id and v2.position == 0


async def test_notes_add_edit_delete(client, db):
    async with db() as session:
        col = (await _columns(session))[0]
        video = Video(drive_file_id="vn", name="vn.mp4", column_id=col.id,
                      position=0, download_status="downloaded")
        session.add(video)
        await session.commit()
        video_id = video.id

    resp = await client.post(f"/videos/{video_id}/notes", data={"body": "first idea"})
    assert resp.status_code == 200
    assert "first idea" in resp.text

    async with db() as session:
        note_id = (await session.execute(select(Note.id))).scalar_one()

    resp = await client.patch(f"/notes/{note_id}", data={"body": "updated idea"})
    assert resp.status_code == 200
    assert "updated idea" in resp.text

    resp = await client.delete(f"/notes/{note_id}")
    assert resp.status_code == 200

    async with db() as session:
        assert (await session.execute(select(Note))).scalars().all() == []
