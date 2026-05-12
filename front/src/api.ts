import type { Deposit, DepositCompareResult, LiveDepositsSyncResponse } from "./types";

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchDeposits(): Promise<Deposit[]> {
  const res = await fetch("/api/v1/deposits/");
  return parseJson<Deposit[]>(res);
}

export interface ComparePayload {
  amount: string;
  term_months: number;
  currency: Deposit["currency"];
  deposit_type: Deposit["deposit_type"];
  inflation_rate_percent?: string;
}

export async function compareDeposits(body: ComparePayload): Promise<DepositCompareResult[]> {
  const res = await fetch("/api/v1/deposits/compare/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson<DepositCompareResult[]>(res);
}

/** Синхронизация с открытыми API банков (кнопка «Обновить каталог» на фронте). */
export async function syncLiveDepositsFromBanks(): Promise<LiveDepositsSyncResponse> {
  const res = await fetch("/api/v1/sync/live-deposits/", { method: "POST" });
  return parseJson<LiveDepositsSyncResponse>(res);
}
