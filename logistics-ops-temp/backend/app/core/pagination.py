from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def _page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


Pagination = Annotated[PageParams, Depends(_page_params)]


def count_rows(db: Session, stmt: Select[Any]) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def apply_page(stmt: Select[Any], params: PageParams) -> Select[Any]:
    return stmt.limit(params.page_size).offset(params.offset)
