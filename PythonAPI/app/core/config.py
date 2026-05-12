"""
Конфигурация приложения (источник переменных окружения и значений по умолчанию).
"""

from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки, читаемые из окружения или .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Строка подключения SQLAlchemy к PostgreSQL (драйвер psycopg v3: postgresql+psycopg://...)
    # Имя переменной в .env: DATABASE_URL. БД по умолчанию — myfin (как в pgAdmin).
    database_url: str = Field(
        default="postgresql+psycopg://aispvi:secret@127.0.0.1:5432/myfin",
        description="URL базы данных PostgreSQL",
    )

    # Справочные вклады USD/EUR (см. app.services.reference_fx_deposits)
    add_reference_usd_eur_catalog: bool = Field(
        default=True,
        description="Добавлять ориентировочные вклады USD/EUR, если API не даёт числовых ставок",
    )
    reference_fx_bank_name: str = Field(
        default="Ориентир USD/EUR",
        description="Наименование банка-заголовка для справочных валютных вкладов",
    )
    reference_usd_nominal_rate_percent: Decimal = Field(
        default=Decimal("3.500"),
        ge=Decimal("0"),
        description="Ориентировочная номинальная ставка справочного вклада USD, % годовых",
    )
    reference_eur_nominal_rate_percent: Decimal = Field(
        default=Decimal("3.000"),
        ge=Decimal("0"),
        description="Ориентировочная номинальная ставка справочного вклада EUR, % годовых",
    )


settings = Settings()
