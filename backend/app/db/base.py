import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPk:
    """Mixin: UUID primary key, generated in Python (not DB) so it's available
    before flush."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def str_enum_column(enum_cls: type[StrEnum], length: int) -> Enum:
    """A portable (native_enum=False -> VARCHAR) column for a StrEnum that
    persists the enum's lowercase *value* ("candidate"), not its *name*
    ("CANDIDATE") — SQLAlchemy's default. See memory.md §6: a bare Enum()
    call stores names, which silently disagrees with every value the API and
    JWT claims use."""
    return Enum(
        enum_cls, native_enum=False, length=length, values_callable=lambda e: [x.value for x in e]
    )
