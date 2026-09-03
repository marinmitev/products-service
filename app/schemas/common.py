from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PaginationParams(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
