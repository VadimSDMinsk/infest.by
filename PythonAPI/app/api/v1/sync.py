"""
Синхронизация каталога вкладов с внешними источниками (открытые API банков).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.live_sync import LiveDepositsSyncResponse
from app.services.live_sync_all import sync_all_live_deposit_sources

router = APIRouter(prefix="/sync", tags=["Синхронизация"])


@router.post(
    "/live-deposits/",
    response_model=LiveDepositsSyncResponse,
    summary="Обновить каталог вкладов из открытых API банков",
)
def sync_live_deposits(db: Session = Depends(get_db)) -> LiveDepositsSyncResponse:
    """
    Загружает актуальные продукты со всех поддерживаемых банковских API.

    На текущий момент: **Беларусбанк** (``belarusbank.by/api/deposits_info``).
    Ранее импортированные строки с ``external_source = belarusbank_api`` для этого банка
    заменяются новой выборкой. Другие записи в БД не затрагиваются.

    Колонки ``external_source`` / ``external_id`` добавляются при старте приложения автоматически.
    """
    try:
        return sync_all_live_deposit_sources(db)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка обращения к API банка: {e}",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except ProgrammingError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Ошибка схемы БД (колонки external_source / external_id). "
                f"Подробности: {e}"
            ),
        ) from e
