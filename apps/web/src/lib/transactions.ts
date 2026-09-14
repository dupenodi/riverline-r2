/**
 * Snapshot the agent pushes over RTVI after every write.
 */

export type MoneyDirection = "incoming" | "outgoing";

export type MoneyItem = {
  id: string;
  direction: MoneyDirection;
  label: string;
  amount: number;
  day: number;
};

export type DerivedMove = {
  id: string;
  label: string;
  amount: number;
  kind: string;
};

export type DerivedDay = {
  date: string;
  in: number;
  out: number;
  closing: number;
  moves: DerivedMove[];
};

export type DerivedState = {
  finish: number;
  crunch: { date: string; amount: number };
  days: DerivedDay[];
};

export type FinanceKind = "income" | "need" | "debt" | "flex" | "owed";

export type FinanceEntry = {
  id: string;
  kind: FinanceKind;
  label: string;
  amount: number | null;
  amount_min: number | null;
  amount_max: number | null;
  day: number | null;
  cadence: string;
  status: string;
  on_date?: string | null;
};

export type PlanStep = {
  action: string;
  label: string;
  amount: number;
  date?: string | null;
  until?: string | null;
  note?: string | null;
};

export type AdvicePayoff = {
  lowest: number;
  date: string;
  ok: boolean;
  finish: number;
};

export type AdviceState = {
  points: string[];
  payoff: AdvicePayoff;
};

export type PlanState = {
  solvable: boolean;
  steps: PlanStep[];
  gap: number | null;
  gap_date: string | null;
};

export type TransactionsState = {
  type: "transactions" | "finance";
  version: number;
  name: string | null;
  cash: number | null;
  items: MoneyItem[];
  entries: FinanceEntry[];
  missing: string[];
  conflicts: string[];
  derived?: DerivedState | null;
  plan: PlanState | null;
  advice: AdviceState | null;
};

export const EMPTY_TRANSACTIONS: TransactionsState = {
  type: "transactions",
  version: 0,
  name: null,
  cash: null,
  items: [],
  entries: [],
  missing: [],
  conflicts: [],
  derived: null,
  plan: null,
  advice: null,
};

function isItem(value: unknown): value is MoneyItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<MoneyItem>;
  return (
    typeof item.id === "string" &&
    (item.direction === "incoming" || item.direction === "outgoing") &&
    typeof item.label === "string" &&
    typeof item.amount === "number" &&
    typeof item.day === "number" &&
    item.day >= 1 &&
    item.day <= 31
  );
}

function isMove(value: unknown): value is DerivedMove {
  if (!value || typeof value !== "object") return false;
  const move = value as Partial<DerivedMove>;
  return (
    typeof move.id === "string" &&
    typeof move.label === "string" &&
    typeof move.amount === "number" &&
    typeof move.kind === "string"
  );
}

function isDerivedDay(value: unknown): value is DerivedDay {
  if (!value || typeof value !== "object") return false;
  const day = value as Partial<DerivedDay>;
  return (
    typeof day.date === "string" &&
    typeof day.in === "number" &&
    typeof day.out === "number" &&
    typeof day.closing === "number" &&
    Array.isArray(day.moves) &&
    day.moves.every(isMove)
  );
}

function isDerived(value: unknown): value is DerivedState {
  if (!value || typeof value !== "object") return false;
  const derived = value as Partial<DerivedState>;
  return (
    typeof derived.finish === "number" &&
    typeof derived.crunch === "object" &&
    derived.crunch != null &&
    typeof derived.crunch.date === "string" &&
    typeof derived.crunch.amount === "number" &&
    Array.isArray(derived.days) &&
    derived.days.length === 30 &&
    derived.days.every(isDerivedDay)
  );
}

const KINDS: FinanceKind[] = ["income", "need", "debt", "flex", "owed"];

function readEntry(value: unknown): FinanceEntry | null {
  if (!value || typeof value !== "object") return null;
  const entry = value as Record<string, unknown>;
  if (typeof entry.id !== "string" || typeof entry.label !== "string") return null;
  if (!KINDS.includes(entry.kind as FinanceKind)) return null;
  return {
    id: entry.id,
    kind: entry.kind as FinanceKind,
    label: entry.label,
    amount: typeof entry.amount === "number" ? entry.amount : null,
    amount_min: typeof entry.amount_min === "number" ? entry.amount_min : null,
    amount_max: typeof entry.amount_max === "number" ? entry.amount_max : null,
    day: typeof entry.day === "number" ? entry.day : null,
    cadence: typeof entry.cadence === "string" ? entry.cadence : "monthly",
    status: typeof entry.status === "string" ? entry.status : "unknown",
    on_date: typeof entry.on_date === "string" ? entry.on_date : null,
  };
}

function isPlan(value: unknown): value is PlanState {
  if (!value || typeof value !== "object") return false;
  const plan = value as Partial<PlanState>;
  return typeof plan.solvable === "boolean" && Array.isArray(plan.steps);
}

function isAdvice(value: unknown): value is AdviceState {
  if (!value || typeof value !== "object") return false;
  const advice = value as Partial<AdviceState>;
  return (
    Array.isArray(advice.points) &&
    typeof advice.payoff === "object" &&
    advice.payoff != null &&
    typeof advice.payoff.lowest === "number" &&
    typeof advice.payoff.date === "string"
  );
}

function isState(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<TransactionsState>;
  return (
    (candidate.type === "transactions" || candidate.type === "finance") &&
    typeof candidate.version === "number"
  );
}

export function acceptTransactions(
  current: TransactionsState,
  incoming: unknown,
): TransactionsState {
  if (!isState(incoming)) return current;
  const raw = incoming as Partial<TransactionsState> & {
    items?: unknown;
    entries?: unknown;
    missing?: unknown;
    conflicts?: unknown;
    cash?: unknown;
  };
  if (typeof raw.version === "number" && raw.version < current.version) {
    return current;
  }
  const derived = isDerived(raw.derived) ? raw.derived : current.derived;
  const items = Array.isArray(raw.items) ? raw.items.filter(isItem) : current.items;
  const entries = Array.isArray(raw.entries)
    ? raw.entries.map(readEntry).filter((e): e is FinanceEntry => e != null)
    : current.entries;
  const missing = Array.isArray(raw.missing)
    ? raw.missing.filter((m): m is string => typeof m === "string")
    : current.missing;
  const conflicts = Array.isArray(raw.conflicts)
    ? raw.conflicts.filter((m): m is string => typeof m === "string")
    : current.conflicts;
  const cash =
    typeof raw.cash === "number"
      ? raw.cash
      : raw.cash === null
        ? null
        : current.cash;
  const plan = isPlan(raw.plan) ? raw.plan : raw.plan === null ? null : current.plan;
  const incomingAdvice = (incoming as { advice?: unknown }).advice;
  const advice = isAdvice(incomingAdvice)
    ? incomingAdvice
    : incomingAdvice === null
      ? null
      : current.advice;
  return {
    type: raw.type === "finance" ? "finance" : "transactions",
    version: raw.version ?? current.version,
    name: typeof raw.name === "string" ? raw.name : current.name,
    cash,
    items,
    entries,
    missing,
    conflicts,
    derived: derived ?? null,
    plan,
    advice,
  };
}

export function hasCalendar(state: TransactionsState): boolean {
  return (state.derived?.days.length ?? 0) > 0 || state.items.length > 0;
}

export function hasBoard(state: TransactionsState): boolean {
  return (
    hasCalendar(state) ||
    state.entries.length > 0 ||
    state.cash != null ||
    state.missing.length > 0 ||
    state.conflicts.length > 0 ||
    state.plan != null ||
    state.advice != null
  );
}

export function money(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

export function formatDay(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return new Date(year, month - 1, day).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
  });
}

export function entryAmount(entry: FinanceEntry): string {
  if (entry.amount != null) return money(entry.amount);
  if (entry.amount_min != null && entry.amount_max != null) {
    return `~${money(entry.amount_min)}–${money(entry.amount_max)}`;
  }
  if (entry.amount_max != null) return `~${money(entry.amount_max)}`;
  if (entry.amount_min != null) return `~${money(entry.amount_min)}`;
  return "—";
}

export function netTotal(items: MoneyItem[]): number {
  return items.reduce((sum, item) => {
    return sum + (item.direction === "incoming" ? item.amount : -item.amount);
  }, 0);
}

export function itemsByDay(items: MoneyItem[]): Map<number, MoneyItem[]> {
  const map = new Map<number, MoneyItem[]>();
  for (const item of items) {
    const list = map.get(item.day) ?? [];
    list.push(item);
    map.set(item.day, list);
  }
  return map;
}

export function dayNet(items: MoneyItem[]): number {
  return netTotal(items);
}
