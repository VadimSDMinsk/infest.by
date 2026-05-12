"""
Схемы ответов для синхронизации каталога вкладов с внешними источниками.
"""

from pydantic import BaseModel, Field


class BankLiveSyncResult(BaseModel):
    """Результат загрузки вкладов с одного источника (банк / открытый API)."""

    source_key: str = Field(..., description="Ключ источника, например belarusbank_api")
    bank_name: str = Field(..., description="Банк, в каталог которого записаны данные")
    removed_previous_live: int = Field(..., ge=0, description="Сколько старых «живых» строк этого источника удалено")
    inserted: int = Field(..., ge=0, description="Сколько новых строк добавлено")
    skipped: int = Field(..., ge=0, description="Сколько позиций пропущено (нет ставки, фильтр и т.п.)")
    message: str = Field(..., description="Пояснение для пользователя")


class LiveDepositsSyncResponse(BaseModel):
    """Сводка по всем подключённым на данный момент живым источникам."""

    results: list[BankLiveSyncResult] = Field(default_factory=list, description="Результаты по каждому источнику")
    summary: str = Field(..., description="Краткое резюме для отображения на фронтенде")
