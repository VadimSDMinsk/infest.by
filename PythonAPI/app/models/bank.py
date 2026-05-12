"""
Модель банка — владелец продуктов «вклад».
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.deposit import Deposit


class Bank(BaseModel):
    """
    Банк, предлагающий вклады.

    Attributes:
        name: Полное или краткое наименование банка (уникальное в каталоге).
        deposits: Связанные вклады (ленивая загрузка по умолчанию).
    """

    __tablename__ = "banks"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False, comment="Наименование банка")

    deposits: Mapped[list[Deposit]] = relationship("Deposit", back_populates="bank", cascade="all, delete-orphan")
