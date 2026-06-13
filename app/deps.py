from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_or_404(session: AsyncSession, model: type[T], id: int) -> T:
    obj = await session.get(model, id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
