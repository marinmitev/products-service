from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

SKU_PATTERN = r"^[A-Z0-9][A-Z0-9._-]{2,63}$"


class ProductCreate(BaseModel):
    sku: str = Field(..., max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=20_000)
    image_url: str | None = Field(default=None, max_length=2048)
    price: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    category_id: int = Field(..., gt=0)

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        import re

        if not re.fullmatch(SKU_PATTERN, value):
            raise ValueError(
                "SKU must be 3-64 characters: start with A-Z or 0-9, then A-Z, 0-9, '.', '_' or '-'"
            )
        return value

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title must not be blank")
        return trimmed

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("image_url must be an http or https URL")
        return value


class ProductUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20_000)
    image_url: str | None = Field(default=None, max_length=2048)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    category_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def reject_sku_change(cls, data: object) -> object:
        if isinstance(data, dict) and "sku" in data:
            raise ValueError("SKU is immutable and cannot be changed")
        return data

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title must not be blank")
        return trimmed

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("image_url must be an http or https URL")
        return value


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    title: str
    description: str
    image_url: str | None
    price: Decimal
    category_id: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        return f"{value:.2f}"


class ProductSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Case-insensitive substring match against title or description.",
        examples=["phone"],
    )
    sku: str | None = Field(
        None,
        max_length=64,
        description="Exact SKU match (case-insensitive on input).",
        examples=["SMART-1"],
    )
    category_id: int | None = Field(
        None,
        gt=0,
        description="Restrict to this category. Includes nested categories by default.",
        examples=[1],
    )
    include_descendants: bool = Field(
        True,
        description="When true (default), category_id also matches every category beneath it.",
    )
    price_min: Decimal | None = Field(
        None,
        ge=0,
        decimal_places=2,
        description="Inclusive lower price bound.",
        examples=["100.00"],
    )
    price_max: Decimal | None = Field(
        None,
        ge=0,
        decimal_places=2,
        description="Inclusive upper price bound.",
        examples=["500.00"],
    )
    sort: Literal["price", "-price", "title", "-title", "created_at", "-created_at"] = Field(
        "-created_at",
        description="Sort field. A leading '-' means descending. Always tie-broken by id.",
    )
    limit: int = Field(20, ge=1, le=100, description="Page size.")
    offset: int = Field(0, ge=0, description="Rows to skip.")

    @model_validator(mode="after")
    def check_price_range(self) -> "ProductSearchParams":
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min must be less than or equal to price_max")
        return self
