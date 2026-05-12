"""
Подключение к БД и фабрика сессий SQLAlchemy.

Проект ориентирован на PostgreSQL; для локальных экспериментов при необходимости
по-прежнему можно указать sqlite:///... в DATABASE_URL.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Параметры подключения: для SQLite нужен check_same_thread, для PostgreSQL — пул и проверка соединений
_is_sqlite = settings.database_url.startswith("sqlite")

# pool_pre_ping: перед выдачей соединения из пула проверяется жива ли сессия с БД (важно для PostgreSQL)
_engine_kwargs: dict = {"pool_pre_ping": True}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Умеренный размер пула для учебного/небольшого продакшена
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def apply_lightweight_schema_fixes() -> None:
    """
    Добавляет в существующую БД недостающие колонки под синхронизацию с внешними API.

    ``create_all`` не изменяет уже созданные таблицы, поэтому для старых установок
    выполняем безопасные ``ADD COLUMN IF NOT EXISTS`` (PostgreSQL / современный SQLite).
    """
    stmts = (
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS external_source VARCHAR(32)",
        "ALTER TABLE deposits ADD COLUMN IF NOT EXISTS external_id VARCHAR(32)",
        "CREATE INDEX IF NOT EXISTS ix_deposits_external_source ON deposits (external_source)",
        "CREATE INDEX IF NOT EXISTS ix_deposits_external_id ON deposits (external_id)",
    )
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))


def get_db() -> Generator[Session, None, None]:
    """
    Зависимость FastAPI: выдаёт сессию БД и гарантирует закрытие после запроса.

    Yields:
        Сессия SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
