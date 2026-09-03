from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_categories_no_self_parent",
        ),
        UniqueConstraint("parent_id", "name", name="uq_categories_parent_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )

    parent: Mapped["Category | None"] = relationship(
        remote_side="Category.id", back_populates="children", lazy="raise"
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent", lazy="raise")
