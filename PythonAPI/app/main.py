"""
Точка входа FastAPI-приложения АИСПВИ.

При старте создаются таблицы в БД, применяются лёгкие правки схемы и выполняется
попытка загрузить вклады из открытых API банков (без демо-сида).
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.v1.deposits import router as deposits_router
from app.api.v1.sync import router as sync_router
from app.database import SessionLocal, apply_lightweight_schema_fixes, engine
from app.models.base import Base
from app.services.live_sync_all import sync_all_live_deposit_sources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Создание таблиц, правки схемы и первичная загрузка вкладов из API банков."""
    from app.models.bank import Bank  # noqa: F401
    from app.models.deposit import Deposit  # noqa: F401

    Base.metadata.create_all(bind=engine)
    apply_lightweight_schema_fixes()

    # Первая загрузка каталога из реальных открытых API (сеть должна быть доступна)
    db: Session = SessionLocal()
    try:
        sync_all_live_deposit_sources(db)
        logger.info("Стартовая синхронизация вкладов из API банков выполнена.")
    except Exception as exc:  # noqa: BLE001 — не блокируем запуск приложения
        logger.warning("Стартовая синхронизация вкладов не выполнена: %s", exc, exc_info=True)
    finally:
        db.close()

    yield


app = FastAPI(
    title="АИСПВИ — API",
    description="Практическая часть: модуль сравнения банковских вкладов (данные из открытых API банков)",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(deposits_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
