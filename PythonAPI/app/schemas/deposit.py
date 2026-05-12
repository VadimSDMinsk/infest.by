"""
Схемы вкладов: CRUD, ответы API и расчётные поля для сравнения продуктов.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from math import pow

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.deposit import Currency, DepositType


# Примерная годовая инфляция по умолчанию для учебной модели (%, годовых)
DEFAULT_INFLATION_RATE_PERCENT: Decimal = Decimal("5.0")


class DepositBase(BaseModel):
    """Общие поля вклада (без идентификаторов и меток времени)."""

    name: str = Field(..., max_length=255, description="Название вклада")
    currency: Currency = Field(..., description="Валюта")
    deposit_type: DepositType = Field(..., description="Тип вклада")
    nominal_rate: Decimal = Field(..., ge=Decimal("0"), description="Номинальная ставка, % годовых")
    min_amount: Decimal = Field(..., ge=Decimal("0"), description="Минимальная сумма")
    max_amount: Decimal | None = Field(None, ge=Decimal("0"), description="Максимальная сумма (None — без лимита)")
    term_months_min: int = Field(..., ge=0, description="Минимальный срок, мес.")
    term_months_max: int = Field(..., ge=0, description="Максимальный срок, мес.")
    capitalization: bool = Field(False, description="Капитализация процентов")
    replenishment: bool = Field(False, description="Возможность пополнения")
    early_withdrawal: bool = Field(False, description="Досрочное расторжение / снятие")
    is_active: bool = Field(True, description="Активен в каталоге")


class DepositCreate(DepositBase):
    """Данные для создания вклада (указывается банк)."""

    bank_id: int = Field(..., ge=1, description="Идентификатор банка")


class DepositResponse(DepositBase):
    """Вклад как возвращается клиенту API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    bank_id: int
    created_at: datetime
    updated_at: datetime
    # Заполняется при загрузке связи bank (для удобства фронтенда)
    bank_name: str | None = Field(default=None, description="Наименование банка, если было подгружено")


class DepositCompareRequest(BaseModel):
    """
    Параметры пользователя для подбора и сравнения вкладов.

    Поле ``inflation_rate_percent`` задаёт допущение по годовой инфляции
    для оценки реальной доходности (учебная модель).
    """

    amount: Decimal = Field(..., gt=Decimal("0"), description="Сумма размещения")
    term_months: int = Field(..., ge=1, description="Срок размещения в месяцах")
    currency: Currency = Field(..., description="Желаемая валюта")
    deposit_type: DepositType = Field(..., description="Желаемый тип вклада")
    inflation_rate_percent: Decimal = Field(
        default=DEFAULT_INFLATION_RATE_PERCENT,
        ge=Decimal("0"),
        description="Допущение: годовая инфляция, % (реальная прибыль и реальная эффективная ставка)",
    )


def _annualized_rate_percent(*, growth_factor: float, years: float) -> Decimal:
    """
    Годовая ставка в %, эквивалентная постоянной сложной капитализации за ``years`` лет.

    Формула: ``((growth_factor)^(1/years) - 1) * 100``.
    """
    if years <= 0 or growth_factor <= 0:
        return Decimal("0")
    eff = pow(growth_factor, 1.0 / years) - 1.0
    return (Decimal(str(eff)) * Decimal("100")).quantize(Decimal("0.001"))


class DepositCompareMetrics(BaseModel):
    """
    Расчётные показатели по вкладу для заданных суммы и срока.

    Итог ``final_amount`` считается по условиям продукта (ежемесячная капитализация номинала / 12
    либо простые проценты). Затем:

    - **nominal_effective_rate** — годовая «эффективная» из фактического **номинального** роста
      (без инфляции), согласованная с тем же денежным потоком.
    - **effective_rate** — годовая **реальная** эффективная ставка: та же аннуализация, но от
      **реального** множителя роста покупательной способности (итог дисконтируется инфляцией π
      за срок: деление на ``(1+π)^years``). При π=0 совпадает с номинальной эффективной.
    """

    model_config = ConfigDict(from_attributes=True)

    nominal_effective_rate: Decimal = Field(
        ...,
        description="Эффективная годовая ставка в номинале, % (без учёта инфляции; из final/principal)",
    )
    effective_rate: Decimal = Field(
        ...,
        description="Эффективная годовая ставка в реальном выражении, % (с учётом π; из real_final/principal)",
    )
    final_amount: Decimal = Field(..., description="Итоговая сумма на конец срока (номинал)")
    real_profit: Decimal = Field(
        ...,
        description="Реальная прибыль: итог в деньгах сегодняшней покупательной способности минус вложение (см. инфляцию)",
    )

    @staticmethod
    def compute(
        *,
        principal: Decimal,
        term_months: int,
        nominal_rate_percent: Decimal,
        capitalization: bool,
        inflation_rate_percent: Decimal,
    ) -> DepositCompareMetrics:
        """
        Рассчитывает итоговую сумму, номинальную и реальную эффективные ставки, реальную прибыль.

        Args:
            principal: Начальная сумма.
            term_months: Срок в месяцах.
            nominal_rate_percent: Номинальная годовая ставка, %.
            capitalization: При True — ежемесячная капитализация по номиналу / 12.
            inflation_rate_percent: Годовая инфляция, % (дисконт номинального итога для реальных величин).

        Returns:
            Набор расчётных метрик.
        """
        p = float(principal)
        n = int(term_months)
        r_annual = float(nominal_rate_percent) / 100.0
        years = n / 12.0

        if capitalization and n > 0:
            r_m = r_annual / 12.0
            growth = pow(1.0 + r_m, n)
            final = Decimal(str(p * growth))
        else:
            # Простые проценты: рост линейно от годовой ставки и доли года
            simple_factor = 1.0 + r_annual * years
            final = Decimal(str(p * simple_factor))

        final = final.quantize(Decimal("0.01"))

        # Номинальный множитель роста за срок → годовая эффективная (без инфляции)
        if p > 0 and years > 0:
            total_factor_nom = float(final / Decimal(str(principal)))
            nominal_effective_rate = _annualized_rate_percent(growth_factor=total_factor_nom, years=years)
        else:
            nominal_effective_rate = Decimal("0")

        # Реальная стоимость итога: номинальный итог, приведённый к «сегодня» (постоянные цены)
        infl = float(inflation_rate_percent) / 100.0
        discount = pow(1.0 + infl, years) if years > 0 else 1.0
        real_final = (final / Decimal(str(discount))).quantize(Decimal("0.01"))
        real_profit = (real_final - principal).quantize(Decimal("0.01"))

        # Реальный множитель роста покупательной способности → годовая эффективная с учётом π
        if float(principal) > 0 and years > 0:
            total_factor_real = float(real_final / principal)
            effective_rate = _annualized_rate_percent(growth_factor=total_factor_real, years=years)
        else:
            effective_rate = Decimal("0")

        return DepositCompareMetrics(
            nominal_effective_rate=nominal_effective_rate,
            effective_rate=effective_rate,
            final_amount=final,
            real_profit=real_profit,
        )


class DepositCompareResult(BaseModel):
    """Элемент результата сравнения: вклад + расчёты + опционально имя банка."""

    model_config = ConfigDict(from_attributes=True)

    deposit: DepositResponse
    metrics: DepositCompareMetrics

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nominal_effective_rate(self) -> Decimal:
        """Номинальная эффективная годовая ставка, % (дублирование из metrics)."""
        return self.metrics.nominal_effective_rate

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_rate(self) -> Decimal:
        """Реальная эффективная годовая ставка, % (дублирование из metrics)."""
        return self.metrics.effective_rate

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_amount(self) -> Decimal:
        """Итоговая сумма (дублирование из metrics)."""
        return self.metrics.final_amount

    @computed_field  # type: ignore[prop-decorator]
    @property
    def real_profit(self) -> Decimal:
        """Реальная прибыль (дублирование из metrics)."""
        return self.metrics.real_profit
