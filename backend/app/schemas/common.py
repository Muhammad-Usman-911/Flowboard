"""Building blocks shared by many schemas."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for response schemas: `from_attributes` lets Pydantic read ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """A page of results. Every list endpoint returns this shape."""

    items: list[T]
    total: int  # total matching rows (ignoring limit/offset), for "page X of Y"
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: int = 50
    offset: int = 0


def page_params(
    limit: Annotated[int, Query(ge=1, le=200, description="Max items to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> PageParams:
    """FastAPI dependency: read and validate `?limit=&offset=` once, reuse everywhere."""
    return PageParams(limit=limit, offset=offset)


class ErrorResponse(BaseModel):
    """Documents our error shape in Swagger."""

    detail: str
    code: str


class Message(BaseModel):
    message: str
