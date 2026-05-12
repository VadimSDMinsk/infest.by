const moneyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const rateFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

/** Форматирует строку с числом (Decimal из API) для отображения */
export function formatMoney(value: string | null | undefined, currency: string): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return `${moneyFmt.format(n)} ${currency}`;
}

export function formatPercent(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return `${rateFmt.format(n)} %`;
}

export const currencyLabel: Record<string, string> = {
  BYN: "BYN",
  USD: "USD",
  EUR: "EUR",
};

export const depositTypeLabel: Record<string, string> = {
  irrevocable: "Безотзывный",
  revocable: "Отзывный",
  demand: "До востребования",
};
