/** Ответ API: один вклад */
export interface Deposit {
  id: number;
  bank_id: number;
  bank_name: string | null;
  name: string;
  currency: "BYN" | "USD" | "EUR";
  deposit_type: "irrevocable" | "revocable" | "demand";
  nominal_rate: string;
  min_amount: string;
  max_amount: string | null;
  term_months_min: number;
  term_months_max: number;
  capitalization: boolean;
  replenishment: boolean;
  early_withdrawal: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DepositCompareMetrics {
  /** Годовая эффективная из номинального итога (без инфляции) */
  nominal_effective_rate: string;
  /** Годовая эффективная в реальном выражении (с учётом инфляции) */
  effective_rate: string;
  final_amount: string;
  real_profit: string;
}

export interface DepositCompareResult {
  deposit: Deposit;
  metrics: DepositCompareMetrics;
  nominal_effective_rate: string;
  effective_rate: string;
  final_amount: string;
  real_profit: string;
}

/** Один банк после POST /api/v1/sync/live-deposits/ */
export interface BankLiveSyncResult {
  source_key: string;
  bank_name: string;
  removed_previous_live: number;
  inserted: number;
  skipped: number;
  message: string;
}

/** Полный ответ синхронизации с API банков */
export interface LiveDepositsSyncResponse {
  results: BankLiveSyncResult[];
  summary: string;
}
