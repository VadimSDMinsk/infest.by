"""
Агрегатор синхронизации вкладов со всеми доступными открытыми API банков.

Сейчас подключён только Беларусбанк (официальный ``/api/deposits_info``).
Другие банки РБ в открытом доступе чаще не публикуют аналогичный JSON без регистрации
в API Store — при появлении стабильного URL добавьте вызов в ``sync_all_live_deposit_sources``.
"""

from __future__ import annotations

import httpx
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.live_sync import BankLiveSyncResult, LiveDepositsSyncResponse
from app.services.belarusbank_live import sync_belarusbank_deposits
from app.services.reference_fx_deposits import sync_reference_fx_deposits


def sync_all_live_deposit_sources(db: Session) -> LiveDepositsSyncResponse:
    """
    Последовательно опрашивает все настроенные живые источники и пишет данные в БД.

    Каждый источник сам делает ``commit`` (как реализовано для Беларусбанка).

    Raises:
        httpx.HTTPError, ValueError, ProgrammingError — пробрасываются наверх для HTTP-ответа API.
    """
    results: list[BankLiveSyncResult] = []

    removed, inserted, skipped, msg = sync_belarusbank_deposits(db)
    results.append(
        BankLiveSyncResult(
            source_key="belarusbank_api",
            bank_name="Беларусбанк",
            removed_previous_live=removed,
            inserted=inserted,
            skipped=skipped,
            message=msg,
        )
    )

    if settings.add_reference_usd_eur_catalog:
        removed2, inserted2, skipped2, msg2 = sync_reference_fx_deposits(db)
        results.append(
            BankLiveSyncResult(
                source_key="reference_fx",
                bank_name=settings.reference_fx_bank_name,
                removed_previous_live=removed2,
                inserted=inserted2,
                skipped=skipped2,
                message=msg2,
            )
        )

    total_ins = sum(r.inserted for r in results)
    total_sk = sum(r.skipped for r in results)
    summary = (
        f"Обновлено источников: {len(results)}. "
        f"Всего добавлено записей: {total_ins}, пропущено позиций: {total_sk}. "
        "Беларусбанк — из публичного API; по USD/EUR в JSON часто только заглушки ставок — "
        "при включённой настройке add_reference_usd_eur_catalog добавляются справочные вклады с ориентировочными %."
    )
    return LiveDepositsSyncResponse(results=results, summary=summary)
