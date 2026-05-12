import { useCallback, useEffect, useMemo, useState } from "react";
import { compareDeposits, fetchDeposits, syncLiveDepositsFromBanks } from "./api";
import { currencyLabel, depositTypeLabel, formatMoney, formatPercent } from "./format";
import type { Deposit, DepositCompareResult } from "./types";

type Tab = "catalog" | "compare";

export function App() {
  const [tab, setTab] = useState<Tab>("catalog");
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const [amount, setAmount] = useState("5000");
  const [termMonths, setTermMonths] = useState(12);
  const [currency, setCurrency] = useState<Deposit["currency"]>("BYN");
  const [depositType, setDepositType] = useState<Deposit["deposit_type"]>("irrevocable");
  const [inflation, setInflation] = useState("5");
  const [compareRows, setCompareRows] = useState<DepositCompareResult[] | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const loadDeposits = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDeposits(await fetchDeposits());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки вкладов");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDeposits();
  }, [loadDeposits]);

  const activeCount = useMemo(() => deposits.filter((d) => d.is_active).length, [deposits]);

  async function handleLiveBankSync() {
    setSyncMsg(null);
    setError(null);
    try {
      await syncLiveDepositsFromBanks();
      setSyncMsg("Каталог успешно обновлён.");
      await loadDeposits();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки данных из банков");
    }
  }

  async function handleCompare(e: React.FormEvent) {
    e.preventDefault();
    setCompareLoading(true);
    setError(null);
    setCompareRows(null);
    try {
      const rows = await compareDeposits({
        amount,
        term_months: termMonths,
        currency,
        deposit_type: depositType,
        inflation_rate_percent: inflation || undefined,
      });
      setCompareRows(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сравнения");
    } finally {
      setCompareLoading(false);
    }
  }

  return (
    <div className="layout">
      <header className="header">
        <div className="header__brand">
          <span className="header__title">Інвеставанне.by</span>
          <span className="header__subtitle">Модуль сравнения банковских вкладов</span>
        </div>
        <div className="header__actions">
          <button type="button" className="btn" onClick={() => void handleLiveBankSync()}>
            Обновить каталог
          </button>
        </div>
      </header>

      {error ? <div className="banner banner--error">{error}</div> : null}
      {syncMsg ? <div className="banner banner--ok">{syncMsg}</div> : null}

      <nav className="tabs" aria-label="Разделы">
        <button
          type="button"
          className={`tabs__btn ${tab === "catalog" ? "tabs__btn--active" : ""}`}
          onClick={() => setTab("catalog")}
        >
          Каталог вкладов
        </button>
        <button
          type="button"
          className={`tabs__btn ${tab === "compare" ? "tabs__btn--active" : ""}`}
          onClick={() => setTab("compare")}
        >
          Сравнение
        </button>
      </nav>

      <main className="main">
        {tab === "catalog" ? (
          <section className="panel">
            <div className="panel__head">
              <h2>Все вклады</h2>
              <span className="muted">
                Записей: {deposits.length}, активных: {activeCount}
              </span>
            </div>
            {loading ? <p className="muted">Загрузка…</p> : null}
            {!loading && deposits.length === 0 ? (
              <p className="muted">
                Каталог пуст. Нажмите «Обновить каталог» или дождитесь загрузки при старте бэкенда (нужен
                доступ в интернет).
              </p>
            ) : null}
            {deposits.length > 0 ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Банк</th>
                      <th>Продукт</th>
                      <th>Валюта</th>
                      <th>Тип</th>
                      <th>Ставка</th>
                      <th>Сумма</th>
                      <th>Срок (мес.)</th>
                      <th>Условия</th>
                      <th>Активен</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deposits.map((d) => (
                      <tr key={d.id}>
                        <td>{d.bank_name ?? `ID ${d.bank_id}`}</td>
                        <td>{d.name}</td>
                        <td>{currencyLabel[d.currency] ?? d.currency}</td>
                        <td>{depositTypeLabel[d.deposit_type] ?? d.deposit_type}</td>
                        <td>{formatPercent(d.nominal_rate)}</td>
                        <td>
                          {formatMoney(d.min_amount, d.currency)}
                          {d.max_amount != null ? ` — ${formatMoney(d.max_amount, d.currency)}` : " — без лимита"}
                        </td>
                        <td>
                          {d.term_months_min}–{d.term_months_max}
                        </td>
                        <td className="flags">
                          {d.capitalization ? <span className="tag">капитализация</span> : null}
                          {d.replenishment ? <span className="tag">пополнение</span> : null}
                          {d.early_withdrawal ? <span className="tag">досрочно</span> : null}
                          {!d.capitalization && !d.replenishment && !d.early_withdrawal ? (
                            <span className="muted">—</span>
                          ) : null}
                        </td>
                        <td>{d.is_active ? "да" : "нет"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        ) : null}

        {tab === "compare" ? (
          <section className="panel">
            <h2>Сравнение по вашим параметрам</h2>
            <p className="muted intro">
              Укажите сумму, срок, валюту и тип вклада. Подходящие активные продукты будут отсортированы по реальной
              прибыли. Эффективные ставки: «ном.» — из фактического номинального итога; «реал.» — годовая ставка роста
              покупательной способности с учётом поля инфляции (дисконт итога на (1+π)^годы, затем аннуализация).
            </p>
            <form className="form" onSubmit={(e) => void handleCompare(e)}>
              <div className="form__grid">
                <label className="field">
                  <span>Сумма размещения</span>
                  <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" required />
                </label>
                <label className="field">
                  <span>Срок, мес.</span>
                  <input
                    type="number"
                    min={1}
                    max={600}
                    value={termMonths}
                    onChange={(e) => setTermMonths(Number(e.target.value))}
                    required
                  />
                </label>
                <label className="field">
                  <span>Валюта</span>
                  <select value={currency} onChange={(e) => setCurrency(e.target.value as Deposit["currency"])}>
                    <option value="BYN">BYN</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </label>
                <label className="field">
                  <span>Тип вклада</span>
                  <select
                    value={depositType}
                    onChange={(e) => setDepositType(e.target.value as Deposit["deposit_type"])}
                  >
                    <option value="irrevocable">Безотзывный</option>
                    <option value="revocable">Отзывный</option>
                    <option value="demand">До востребования</option>
                  </select>
                </label>
                <label className="field field--wide">
                  <span>Инфляция (годовых, %)</span>
                  <input value={inflation} onChange={(e) => setInflation(e.target.value)} inputMode="decimal" />
                </label>
              </div>
              <div className="form__actions">
                <button type="submit" className="btn" disabled={compareLoading}>
                  {compareLoading ? "Считаем…" : "Сравнить"}
                </button>
              </div>
            </form>

            {compareRows && compareRows.length === 0 ? (
              <p className="muted">Нет вкладов, подходящих под заданные условия.</p>
            ) : null}

            {compareRows && compareRows.length > 0 ? (
              <div className="table-wrap table-wrap--mt">
                <table className="table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Банк</th>
                      <th>Продукт</th>
                      <th>Номинал</th>
                      <th>Эфф. ном.</th>
                      <th>Эфф. реал.</th>
                      <th>Итог</th>
                      <th>Реал. прибыль</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareRows.map((row, i) => (
                      <tr key={row.deposit.id}>
                        <td>{i + 1}</td>
                        <td>{row.deposit.bank_name ?? `ID ${row.deposit.bank_id}`}</td>
                        <td>{row.deposit.name}</td>
                        <td>{formatPercent(row.deposit.nominal_rate)}</td>
                        <td>{formatPercent(row.metrics.nominal_effective_rate)}</td>
                        <td>{formatPercent(row.metrics.effective_rate)}</td>
                        <td>{formatMoney(row.metrics.final_amount, row.deposit.currency)}</td>
                        <td className="num-strong">{formatMoney(row.metrics.real_profit, row.deposit.currency)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        ) : null}
      </main>

      <footer className="footer">
        <span>Бэкенд: FastAPI :8000 · фронт: Vite :5173 · данные: открытые API банков (прокси /api)</span>
      </footer>
    </div>
  );
}
