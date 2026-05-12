"""
Модель банковского вклада и перечисления валюты / типа вклада.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.bank import Bank


def _sql_enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Возвращает строковые значения перечисления для колонки SQLAlchemy Enum."""
    return [member.value for member in enum_cls]


class Currency(StrEnum):
    """Допустимые валюты вклада (российский рубль не используется)."""

    BYN = "BYN"
    USD = "USD"
    EUR = "EUR"


class DepositType(StrEnum):
    """Тип вклада по условиям снятия и срока."""

    irrevocable = "irrevocable"  # безотзывный
    revocable = "revocable"  # отзывный
    demand = "demand"  # до востребования


class Deposit(BaseModel):
    """
    Банковский вклад с параметрами для сравнения и отбора.

    Ставка ``nominal_rate`` задаётся в процентах годовых (номинальных).
    Поля ``min_amount`` / ``max_amount`` ограничивают сумму размещения;
    ``max_amount`` может быть NULL, если верхнего предела нет.
    """

    __tablename__ = "deposits"

    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), nullable=False, index=True, comment="Банк-эмитент вклада")

    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Название вкладного продукта")

    # native_enum=False — хранение строкой (удобно для SQLite в учебном проекте)
    currency: Mapped[Currency] = mapped_column(
        SAEnum(Currency, native_enum=False, length=8, values_callable=_sql_enum_values),
        nullable=False,
        comment="Валюта вклада",
    )

    deposit_type: Mapped[DepositType] = mapped_column(
        SAEnum(DepositType, native_enum=False, length=32, values_callable=_sql_enum_values),
        nullable=False,
        comment="Тип вклада: безотзывный, отзывный, до востребования",
    )

    nominal_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, comment="Номинальная ставка, % годовых")

    min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, comment="Минимальная сумма размещения")
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True, comment="Максимальная сумма (NULL — без ограничения)")

    term_months_min: Mapped[int] = mapped_column(Integer, nullable=False, comment="Минимальный срок в месяцах")
    term_months_max: Mapped[int] = mapped_column(Integer, nullable=False, comment="Максимальный срок в месяцах")

    capitalization: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Начисление процентов с капитализацией")
    replenishment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Допускается пополнение")
    early_withdrawal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Досрочное расторжение / частичное снятие")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True, comment="Продукт доступен в каталоге")

    # Пометка строк, загруженных из внешнего API (чтобы при повторной синхронизации заменять только «живые» строки)
    external_source: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        comment="Источник данных: например belarusbank_api; NULL — запись не из автосинхронизации",
    )
    external_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        comment="Идентификатор продукта у внешнего источника (например vklad_id Беларусбанка)",
    )

    bank: Mapped[Bank] = relationship("Bank", back_populates="deposits")
