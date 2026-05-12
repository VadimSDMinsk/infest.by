"""
Загрузка актуального каталога вкладов с открытого API Беларусбанка.

Документация банка: https://belarusbank.by/o-banke/for-developers/informatsionnye-api/api_depozity/

Ответ API — JSON: либо массив объектов, либо объект-словарь с ключами ``vklad_id``.
Часть продуктов содержит рекламные/заглушечные ставки вида «до 0,01%» — такие строки отбрасываются.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.bank import Bank
from app.models.deposit import Currency, Deposit, DepositType

BELARUSBANK_API_URL = "https://belarusbank.by/api/deposits_info"
BELARUSBANK_BANK_NAME = "Беларусбанк"
EXTERNAL_SOURCE = "belarusbank_api"

# Минимальная осмысленная номинальная ставка, % (ниже — заглушки вроде 0,01% на сайте)
MIN_MEANINGFUL_RATE_PERCENT = Decimal("0.15")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _as_str(value: object) -> str:
    """Приводит значение из JSON к строке."""
    if value is None:
        return ""
    return str(value).strip()


def _extract_numbers_percent(text: str) -> list[Decimal]:
    """Извлекает все числа из строки с процентами (поддержка запятой как десятичного разделителя)."""
    if not text:
        return []
    # Заменяем запятую на точку для чисел вида 9,6
    normalized = text.replace(",", ".")
    found: list[Decimal] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)", normalized):
        try:
            found.append(Decimal(m.group(1)))
        except InvalidOperation:
            continue
    return found


def _pick_nominal_rate_percent(vklad_procent: str, vklad_procent_formula: str) -> Decimal | None:
    """Выбирает оценку номинальной ставки как максимум из чисел в полях процента (консервативно для «до X%»)."""
    nums = _extract_numbers_percent(vklad_procent) + _extract_numbers_percent(vklad_procent_formula)
    if not nums:
        return None
    return max(nums)


def _parse_term_months(
    vklad_srok: str,
    vklad_srok_type: str,
    vklad_srok_text: str,
) -> tuple[int, int]:
    """
    Возвращает (min, max) срок в месяцах.

    Сначала пытаемся разобрать русский текст («от 3 до 36 месяцев», «5 лет»),
    затем — поля vklad_srok + vklad_srok_type (d/m/y).
    """
    text = (vklad_srok_text or "").lower().strip()
    # «от 13 до 36 месяцев»
    m = re.search(r"от\s*(\d+)\s*до\s*(\d+)\s*месяц", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return min(a, b), max(a, b)
    # «5 лет»
    m = re.search(r"(\d+)\s*лет", text)
    if m:
        months = int(m.group(1)) * 12
        return months, months
    # «365 дней» и т.п.
    m = re.search(r"(\d+)\s*дн", text)
    if m:
        days = int(m.group(1))
        months = max(1, int(round(days / 30)))
        return months, months

    srok = _as_str(vklad_srok)
    stype = _as_str(vklad_srok_type).lower()
    if srok.isdigit():
        n = int(srok)
        if stype == "y":
            months = n * 12
            return months, months
        if stype == "d":
            months = max(1, int(round(n / 30)))
            return months, months
        # по умолчанию — месяцы
        return n, n

    # Запасной вариант для нестандартных описаний
    return 1, 36


def _parse_currency(vklad_val: str) -> Currency | None:
    """Берёт первую валюту из поля vklad_val (часто дублируется: USD,USD,USD)."""
    raw = _as_str(vklad_val)
    if not raw:
        return None
    first = raw.split(",")[0].strip().upper()
    try:
        return Currency(first)
    except ValueError:
        return None


def _capitalization_from_code(vklad_kapital: str) -> bool:
    """
    Капитализация по коду банка: 1 — в конце срока (без периодической капитализации в нашей модели = false).

    Пустое значение трактуем как отсутствие периодической капитализации (false).
    """
    code = _as_str(vklad_kapital)
    if code == "" or code == "1":
        return False
    return code not in ("", "1")


def _deposit_type_from_text(name: str) -> DepositType:
    """Грубая эвристика по названию продукта (API не отдаёт enum отдельным полем)."""
    n = name.lower()
    if "до востребован" in n or "до востребования" in n:
        return DepositType.demand
    if "отзывн" in n:
        return DepositType.revocable
    return DepositType.irrevocable


def _flags_from_text(name: str, info: str) -> tuple[bool, bool]:
    """Пополнение и досрочность по ключевым словам в названии/описании."""
    blob = f"{name}\n{info}".lower()
    replenishment = "пополнен" in blob
    early = "досрочн" in blob or "отзывн" in blob
    return replenishment, early


def _iter_api_items(payload: Any) -> list[dict[str, Any]]:
    """Нормализует корень JSON к списку словарей продуктов."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        # Частый формат: {"6079": {...}, "6080": {...}}
        return [v for v in payload.values() if isinstance(v, dict)]
    return []


def fetch_belarusbank_payload() -> list[dict[str, Any]]:
    """
    Запрашивает у Беларусбанка JSON и объединяет ответы по нескольким комбинациям валют.

    Отдельные запросы (например только ``BYN``) иногда возвращают другой набор продуктов,
    чем общий ``BYN,USD,EUR`` — объединяем по ``vklad_id`` без дублей.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Language": "ru-BY,ru;q=0.9"}
    merged: dict[str, dict[str, Any]] = {}
    param_variants = ("BYN,USD,EUR", "BYN", "USD", "EUR")

    with httpx.Client(timeout=40.0, follow_redirects=True) as client:
        for deposit_currency in param_variants:
            try:
                resp = client.get(
                    BELARUSBANK_API_URL,
                    params={"deposit_currency": deposit_currency},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                continue
            for item in _iter_api_items(data):
                ext_id = _as_str(item.get("vklad_id"))
                if ext_id and ext_id not in merged:
                    merged[ext_id] = item

    items = list(merged.values())
    if not items:
        raise ValueError("API Беларусбанка вернуло пустой список продуктов (проверьте параметры или доступность сервиса).")
    return items


def sync_belarusbank_deposits(db: Session) -> tuple[int, int, int, str]:
    """
    Удаляет ранее импортированные строки ``belarusbank_api`` для банка «Беларусбанк» и записывает новые.

    Returns:
        Кортеж (удалено_старых, добавлено, пропущено, сообщение_пользователю).
    """
    items = fetch_belarusbank_payload()

    inserted = 0
    skipped = 0
    skip_reasons: list[str] = []

    try:
        bank = db.execute(select(Bank).where(Bank.name == BELARUSBANK_BANK_NAME)).scalar_one_or_none()
        if bank is None:
            bank = Bank(name=BELARUSBANK_BANK_NAME)
            db.add(bank)
            db.flush()

        res = db.execute(delete(Deposit).where(Deposit.bank_id == bank.id, Deposit.external_source == EXTERNAL_SOURCE))
        removed = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0

        for raw in items:
            ext_id = _as_str(raw.get("vklad_id"))
            name = _as_str(raw.get("vklad_name"))[:255]
            if not ext_id or not name:
                skipped += 1
                continue

            currency = _parse_currency(_as_str(raw.get("vklad_val")))
            if currency is None:
                skipped += 1
                skip_reasons.append(f"id {ext_id}: неизвестная валюта")
                continue

            rate = _pick_nominal_rate_percent(
                _as_str(raw.get("vklad_procent")),
                _as_str(raw.get("vklad_procent_formula")),
            )
            if rate is None or rate < MIN_MEANINGFUL_RATE_PERCENT:
                skipped += 1
                continue

            tmin, tmax = _parse_term_months(
                _as_str(raw.get("vklad_srok")),
                _as_str(raw.get("vklad_srok_type")),
                _as_str(raw.get("vklad_srok_text")),
            )

            min_raw = raw.get("vklad_minimal")
            try:
                min_amount = (
                    Decimal(str(min_raw)) if min_raw is not None and str(min_raw).strip() != "" else Decimal("0")
                )
            except InvalidOperation:
                min_amount = Decimal("0")
            if min_amount < 0:
                min_amount = Decimal("0")

            cap = _capitalization_from_code(_as_str(raw.get("vklad_kapital")))
            info_blob = (
                _as_str(raw.get("vklad_info"))
                + _as_str(raw.get("vklad_info_dohod"))
                + _as_str(raw.get("vklad_info_preimuchestvo"))
            )
            repl, early = _flags_from_text(name, info_blob)
            dep_type = _deposit_type_from_text(name)

            db.add(
                Deposit(
                    bank_id=bank.id,
                    name=name,
                    currency=currency,
                    deposit_type=dep_type,
                    nominal_rate=rate.quantize(Decimal("0.001")),
                    min_amount=min_amount.quantize(Decimal("0.01")),
                    max_amount=None,
                    term_months_min=tmin,
                    term_months_max=tmax,
                    capitalization=cap,
                    replenishment=repl,
                    early_withdrawal=early,
                    is_active=True,
                    external_source=EXTERNAL_SOURCE,
                    external_id=ext_id[:32],
                )
            )
            inserted += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    msg = (
        f"Источник: открытое API Беларусбанка. Добавлено записей: {inserted}. "
        f"Пропущено без импорта: {skipped}. "
        "Позиции с нечисловой или слишком низкой ставкой (часто «до 0,01%» у валютных вкладов в ответе API) не попадают в каталог."
    )
    if skip_reasons:
        msg += " Примеры пропусков: " + "; ".join(skip_reasons[:5]) + ("…" if len(skip_reasons) > 5 else "")

    return int(removed), inserted, skipped, msg
