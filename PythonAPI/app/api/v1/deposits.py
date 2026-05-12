"""
Роутер вкладов: каталог, карточка вклада и сравнение по параметрам клиента.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.deposit import Deposit
from app.schemas.deposit import (
    DepositCompareMetrics,
    DepositCompareRequest,
    DepositCompareResult,
    DepositResponse,
)

router = APIRouter(prefix="/deposits", tags=["Вклады"])


def _to_deposit_response(row: Deposit) -> DepositResponse:
    """Преобразует ORM-объект вклада в схему ответа с опциональным именем банка."""
    bank_name = row.bank.name if getattr(row, "bank", None) is not None else None
    base = DepositResponse.model_validate(row, from_attributes=True)
    return base.model_copy(update={"bank_name": bank_name})


@router.get("/", response_model=list[DepositResponse], summary="Список вкладов")
def list_deposits(db: Session = Depends(get_db)) -> list[DepositResponse]:
    """
    Возвращает все вклады из каталога (включая неактивные — фильтрация по фронтенду при необходимости).

    Связь с банком подгружается одним запросом (joined load).
    """
    stmt = select(Deposit).options(joinedload(Deposit.bank)).order_by(Deposit.id)
    rows = db.scalars(stmt).unique().all()
    return [_to_deposit_response(d) for d in rows]


@router.get("/{deposit_id}", response_model=DepositResponse, summary="Вклад по идентификатору")
def get_deposit(deposit_id: int, db: Session = Depends(get_db)) -> DepositResponse:
    """Возвращает один вклад или 404, если запись не найдена."""
    stmt = select(Deposit).options(joinedload(Deposit.bank)).where(Deposit.id == deposit_id)
    row = db.scalars(stmt).unique().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вклад не найден")
    return _to_deposit_response(row)


@router.post("/compare/", response_model=list[DepositCompareResult], summary="Сравнение вкладов")
def compare_deposits(payload: DepositCompareRequest, db: Session = Depends(get_db)) -> list[DepositCompareResult]:
    """
    Подбирает активные вклады по валюте, типу, сумме и сроку; для каждого считает метрики доходности.

    Сортировка: по убыванию реальной прибыли (``real_profit``) с учётом допущения по инфляции.
    """
    amount = payload.amount
    term = payload.term_months

    stmt = (
        select(Deposit)
        .options(joinedload(Deposit.bank))
        .where(
            Deposit.is_active.is_(True),
            Deposit.currency == payload.currency,
            Deposit.deposit_type == payload.deposit_type,
            Deposit.min_amount <= amount,
            or_(Deposit.max_amount.is_(None), Deposit.max_amount >= amount),
            Deposit.term_months_min <= term,
            Deposit.term_months_max >= term,
        )
    )
    rows = db.scalars(stmt).unique().all()

    results: list[DepositCompareResult] = []
    for dep in rows:
        metrics = DepositCompareMetrics.compute(
            principal=amount,
            term_months=term,
            nominal_rate_percent=dep.nominal_rate,
            capitalization=dep.capitalization,
            inflation_rate_percent=payload.inflation_rate_percent,
        )
        dep_schema = _to_deposit_response(dep)
        results.append(DepositCompareResult(deposit=dep_schema, metrics=metrics))

    results.sort(key=lambda r: r.metrics.real_profit, reverse=True)
    return results
