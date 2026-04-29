/**
 * Typed client for the Apollo / Pantheon backend.
 * All endpoints live on FastAPI :8001. Override with NEXT_PUBLIC_APOLLO_API.
 */

const BASE_URL = process.env.NEXT_PUBLIC_APOLLO_API ?? "http://localhost:8001";

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 30000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText} — ${detail.slice(0, 200)}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

// ── Shared types ────────────────────────────────────────────────────────────

export type Account = {
  id: number;
  name: string;
  account_type: string;
  is_debt: boolean;
  balance: number;
  current_balance_override: number | null;
  starting_balance: number;
  sort_order: number;
};

export type Transaction = {
  id: number;
  date: string;
  description: string;
  category: string;
  amount: number;
  type: string;
  notes: string | null;
  account: string;
  account_id: number;
  to_account: string | null;
  to_account_id: number | null;
};

export type Holding = {
  id: number;
  symbol: string;
  display_name: string;
  asset_type: string;
  account: string;
  account_id: number;
  amount_invested: number;
  quantity: number;
  avg_price: number;
  coingecko_id: string | null;
};

export type SpendingRow = { category: string; total: number; count: number };

export type DailyReport = Record<string, unknown> & { report_date: string };

export type BlackBookSnapshot = {
  connected: boolean;
  accounts: Account[];
  balances: Account[];
  recent_transactions: Transaction[];
  spending_month: SpendingRow[];
  reports: DailyReport[];
  net_worth: number;
  total_assets: number;
  total_debt: number;
  daily_food_left: number;
  weekly_food_left: number;
  daily_food_budget: number;
  weekly_food_budget: number;
  lifetime_surplus: number;
  runway_days: number;
  daily_burn: number;
  txns_today: number;
  error?: string;
};

export type MaridianQuestion = string | { question: string; tag?: string };

export type MaridianTheme = {
  title: string;
  path: string;
  updated_at: string;
  preview: string;
};

export type MaridianSnapshot = {
  connected: boolean;
  locked: boolean;
  state: Record<string, unknown>;
  today_questions: MaridianQuestion[];
  today_question_file: string;
  top_themes: MaridianTheme[];
  index_excerpt: string;
  last_cycle: string | null;
  cycle_count: number;
  entries_processed: number;
  error?: string;
};

export type MaridianCycleStatus = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  last_result: string | null;
  last_error: string;
};

export type OlympusPerformance = {
  total_trades?: number;
  winners?: number;
  losers?: number;
  win_rate_pct?: number;
  avg_r_multiple?: number;
  total_pnl?: number;
  avg_pnl?: number;
  avg_hold_minutes?: number;
  first_trade_at?: string;
  last_trade_at?: string;
};

export type OlympusTrade = {
  symbol: string;
  direction: string;
  realized_pnl: number;
  r_multiple: number | null;
  exit_reason: string;
  exit_time: string;
};

export type OlympusEvent = {
  event_time: string;
  event_type: string;
  symbol: string | null;
  description: string;
};

export type OlympusCycle = {
  cycle_id: string;
  cycle_timestamp: string;
  universe_size: number;
  scored_count: number;
  error_count: number;
  duration_seconds?: number;
  top_longs: Array<{ symbol: string; score: number; rank: number }>;
  top_shorts: Array<{ symbol: string; score: number; rank: number }>;
};

export type OlympusSnapshot = {
  connected: boolean;
  db_exists: boolean;
  db_path: string;
  db_updated_at: string | null;
  report_path: string;
  report_updated_at: string | null;
  log_updated_at: string | null;
  performance: OlympusPerformance;
  latest_cycle: OlympusCycle | null;
  recent_trades: OlympusTrade[];
  recent_events: OlympusEvent[];
  report_excerpt: string;
  error?: string;
};

export type OverviewSnapshot = {
  health: Record<string, string>;
  latest_signal?: string;
  vault?: { self_model_excerpt?: string };
};

export type ChatResponse = {
  response: string;
  history_length: number;
};

export type AgendaItem = { label: string; date: string; source: string };

// ── Endpoint functions ──────────────────────────────────────────────────────

export const api = {
  // Pantheon overview
  overview: () => request<OverviewSnapshot>("/pantheon/overview"),

  // BlackBook
  blackbookSnapshot: () => request<BlackBookSnapshot>("/pantheon/blackbook"),
  transactions: (limit = 200) =>
    request<{ transactions: Transaction[] }>(`/pantheon/blackbook/transactions?limit=${limit}`),
  createTransaction: (body: {
    amount: number;
    description: string;
    category: string;
    account: string;
    tx_type?: string;
    to_account?: string | null;
    date?: string | null;
    notes?: string;
  }) =>
    request<BlackBookSnapshot>("/pantheon/blackbook/transactions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteTransaction: (id: number) =>
    request<BlackBookSnapshot>(`/pantheon/blackbook/transactions/${id}`, {
      method: "DELETE",
    }),
  setBalanceOverride: (accountId: number, override: number | null) =>
    request<BlackBookSnapshot>(`/pantheon/blackbook/accounts/${accountId}/balance`, {
      method: "POST",
      body: JSON.stringify({ override }),
    }),
  holdings: () =>
    request<{
      holdings: Holding[];
      portfolio_value: number;
      portfolio_pnl: number;
      last_refresh: string;
    }>("/pantheon/blackbook/holdings"),
  refreshHoldings: () =>
    request<{
      holdings: Holding[];
      portfolio_value: number;
      portfolio_pnl: number;
      last_refresh: string;
    }>("/pantheon/blackbook/holdings/refresh", { method: "POST" }),
  allocation: (limit = 10) =>
    request<{ snapshots: Array<Record<string, unknown>> }>(
      `/pantheon/blackbook/allocation?limit=${limit}`,
    ),
  saveAllocation: (payload: Record<string, unknown>) =>
    request<{ snapshots: Array<Record<string, unknown>> }>("/pantheon/blackbook/allocation", {
      method: "POST",
      body: JSON.stringify({ payload }),
    }),
  reports: (limit = 30) =>
    request<{ reports: DailyReport[] }>(`/pantheon/blackbook/reports?limit=${limit}`),
  agenda: () => request<{ items: AgendaItem[] }>("/pantheon/blackbook/agenda"),
  advisor: (message: string) =>
    request<{ response: string; sources: unknown[]; audit_id: string }>(
      "/pantheon/blackbook/advisor",
      { method: "POST", body: JSON.stringify({ message }) },
      120000,
    ),

  // Maridian
  maridianSnapshot: () => request<MaridianSnapshot>("/pantheon/maridian"),
  maridianCycleStatus: () => request<MaridianCycleStatus>("/pantheon/maridian/cycle/status"),
  runMaridianCycleAsync: () =>
    request<{ status: string }>("/pantheon/maridian/run-cycle/async", { method: "POST" }),

  // Olympus
  olympusSnapshot: () => request<OlympusSnapshot>("/pantheon/olympus"),

  // Apollo chat
  chat: (message: string, channel: "ui" | "voice" = "ui") =>
    request<ChatResponse>(
      "/chat",
      { method: "POST", body: JSON.stringify({ message, channel }) },
      180000,
    ),
  resetChat: () =>
    request<ChatResponse>(
      "/chat",
      { method: "POST", body: JSON.stringify({ message: "", reset_history: true }) },
      5000,
    ),
};
