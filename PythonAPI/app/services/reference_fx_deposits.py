"""
Справочные вклады в USD и EUR.

В открытом API Беларусбанка по валютным продуктам часто приходят только «рекламные»
ставки вида «до 0,01%» без реальной числовой доходности, поэтому они не попадают в импорт.
Чтобы модуль сравнения работал и по валюте, добавляются две **ориентировочные** позиции
с числовыми ставками из настроек (их можно задать в .env под актуальный рынок).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bank import Bank
from app.models.deposit import Currency, Deposit, DepositType

REFERENCE_SOURCE = "reference_fx"


def sync_reference_fx_deposits(db: Session) -> tuple[int, int, int, str]:
    """
    Перезаписывает справочные вклады USD/EUR (один банк-«ориентир», две строки).

    Returns:
        Кортеж (удалено_старых, добавлено, пропущено, сообщение).
    """
    if not settings.add_reference_usd_eur_catalog:
        return 0, 0, 0, "Справочные вклады USD/EUR отключены (add_reference_usd_eur_catalog=false)."

    bank = db.execute(select(Bank).where(Bank.name == settings.reference_fx_bank_name)).scalar_one_or_none()
    if bank is None:
        bank = Bank(name=settings.reference_fx_bank_name)
        db.add(bank)
        db.flush()

    res = db.execute(delete(Deposit).where(Deposit.bank_id == bank.id, Deposit.external_source == REFERENCE_SOURCE))
    removed = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0

    specs: list[tuple[Currency, str, Decimal]] = [
        (Currency.USD, "Вклад USD (ориентировочная ставка для сравнения)", settings.reference_usd_nominal_rate_percent),
        (Currency.EUR, "Вклад EUR (ориентировочная ставка для сравнения)", settings.reference_eur_nominal_rate_percent),
    ]

    for cur, title, rate in specs:
        db.add(
            Deposit(
                bank_id=bank.id,
                name=title[:255],
                currency=cur,
                deposit_type=DepositType.irrevocable,
                nominal_rate=rate.quantize(Decimal("0.001")),
                min_amount=Decimal("100.00"),
                max_amount=None,
                term_months_min=1,
                term_months_max=36,
                capitalization=False,
                replenishment=False,
                early_withdrawal=False,
                is_active=True,
                external_source=REFERENCE_SOURCE,
                external_id=f"ref_{cur.value}",
            )
        )

    db.commit()
    msg = (
        f"Добавлены справочные вклады {Currency.USD.value} и {Currency.EUR.value} "
        f"({settings.reference_fx_bank_name}): ставки из настроек приложения, "
        "т.к. публичный API банка не отдаёт осмысленные числовые % по этим валютам."
    )
    return int(removed), 2, 0, msg
