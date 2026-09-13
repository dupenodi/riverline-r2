/**
 * The finance snapshot, as the agent sends it, and the store that holds it.
 *
 * Nothing here computes money. The server sends one versioned snapshot after
 * every change and the cards render it; a second implementation of the maths
 * in the browser could disagree with the tested one, and then the assignment's
 * claim that the calculations are testable would stop being true.
 *
 * Mirrors `snapshot()` in apps/agent/tools.py.
 */

export type FactKind = "balance" | "income" | "essential" | "debt" | "optional";
export type Certainty = "known" | "estimated";
export type FactStatus = "due" | "already_paid";
export type Frequency = "monthly" | "weekly" | "quarterly" | "one_time";

export type Fact = {
  id: string;
  kind: FactKind;
  label: string;
  amount: number | null;
  amount_min: number | null;
  amount_max: number | null;
  day: number | null;
  day_min: number | null;
  day_max: number | null;
  frequency: Frequency;
  minimum_due: number | null;
  status: FactStatus;
  certainty: Certainty;
};

export type Conflict = {
  fact_id: string;
  label: string;
  previous: number;
  current: number;
};

export type Movement = {
  fact_id: string;
  label: string;
  amount: number;
  kind: string;
  certainty: Certainty;
};

export type ActionKind = "pay" | "cut_optional" | "pay_minimum" | "shortfall";

export type PlanAction = {
  kind: ActionKind;
  label: string;
  detail: string;
  amount: number;
  /** Which fact this came from, so the ledger row can be marked. Empty for shortfalls. */
  fact_id: string;
};

export type DayCell = {
  day: string; // ISO date
  index: number;
  in: number;
  out: number;
  balance: number;
  movements: Movement[];
};

export type Plan = {
  start: string;
  opening_balance: number;
  total_in: number;
  total_out: number;
  net: number;
  min_balance: number;
  crunch_day: string | null;
  shortfall: number;
  solvable: boolean;
  cut: Movement[];
  actions: PlanAction[];
  timeline: DayCell[];
};

/**
 * What one group of facts adds up to, as the agent computed it.
 *
 * Sent rather than summed here: the total uses the same `planning_amount` the
 * planner uses, so the rail can never show a friendlier figure than the plan
 * is working with. `estimated` is true if any member of the group was a guess
 * or a range.
 */
export type GroupTotal = {
  amount: number | null;
  estimated: boolean;
  count: number;
};

export type FinanceSnapshot = {
  type: "finance_state";
  version: number;
  /** The user's first name, once they have given it. */
  name: string | null;
  facts: Fact[];
  totals: Record<FactKind, GroupTotal>;
  conflicts: Conflict[];
  missing: string[];
  would_sharpen: string[];
  /** The month as it stands, updated on every turn. Null until a balance is known. */
  projection: Plan | null;
  /** The finished plan. Null until the user has actually asked for one. */
  plan: Plan | null;
};

const EMPTY_TOTAL: GroupTotal = { amount: null, estimated: false, count: 0 };

export const EMPTY_SNAPSHOT: FinanceSnapshot = {
  type: "finance_state",
  // Below the agent's first version, which is 0 — the opening publish, sent
  // before a single number has been said. At 0 the acceptance check below
  // would drop it and the panel would sit blank until the first fact landed.
  version: -1,
  name: null,
  facts: [],
  totals: {
    balance: EMPTY_TOTAL,
    income: EMPTY_TOTAL,
    essential: EMPTY_TOTAL,
    debt: EMPTY_TOTAL,
    optional: EMPTY_TOTAL,
  },
  conflicts: [],
  missing: [],
  would_sharpen: [],
  projection: null,
  plan: null,
};

function isSnapshot(value: unknown): value is FinanceSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<FinanceSnapshot>;
  return (
    candidate.type === "finance_state" &&
    typeof candidate.version === "number" &&
    Array.isArray(candidate.facts)
  );
}

/**
 * Accept a snapshot only if it is newer than the one on screen.
 *
 * Frames can arrive out of order, and a late one carrying an older version
 * would silently roll the user's numbers back — the exact drift between the
 * conversation and the cards this design exists to prevent.
 */
export function acceptSnapshot(
  current: FinanceSnapshot,
  incoming: unknown,
): FinanceSnapshot {
  if (!isSnapshot(incoming)) return current;
  if (incoming.version <= current.version) return current;
  return {
    ...EMPTY_SNAPSHOT,
    ...incoming,
    name: incoming.name ?? null,
    facts: incoming.facts ?? [],
    totals: { ...EMPTY_SNAPSHOT.totals, ...(incoming.totals ?? {}) },
    conflicts: incoming.conflicts ?? [],
    missing: incoming.missing ?? [],
    would_sharpen: incoming.would_sharpen ?? [],
  };
}

/** The plan if there is one, otherwise the live forecast. */
export function currentPlan(snapshot: FinanceSnapshot): Plan | null {
  return snapshot.plan ?? snapshot.projection;
}

export function factsOfKind(snapshot: FinanceSnapshot, kind: FactKind): Fact[] {
  return snapshot.facts.filter((fact) => fact.kind === kind);
}

/** What a group adds up to. Never recomputed here — see `GroupTotal`. */
export function groupTotal(
  snapshot: FinanceSnapshot,
  kind: FactKind,
): GroupTotal {
  return snapshot.totals?.[kind] ?? EMPTY_TOTAL;
}

export function hasAnything(snapshot: FinanceSnapshot): boolean {
  return snapshot.facts.length > 0;
}

// --- formatting --------------------------------------------------------------

const rupees = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

/** `₹24,000`. Negative amounts read as `-₹2,400`, never `₹-2,400`. */
export function money(amount: number): string {
  const sign = amount < 0 ? "-" : "";
  return `${sign}₹${rupees.format(Math.abs(Math.round(amount)))}`;
}

/**
 * What a fact is worth, as words rather than a single number.
 *
 * A range stays a range and an estimate keeps its `~`. Flattening either one
 * into a tidy figure would show the user a precision they never gave us.
 */
export function factAmount(fact: Fact): string {
  const tilde = fact.certainty === "estimated" ? "~" : "";
  if (fact.amount != null) return `${tilde}${money(fact.amount)}`;
  if (fact.amount_min != null && fact.amount_max != null) {
    return `${money(fact.amount_min)}–${money(fact.amount_max)}`;
  }
  if (fact.amount_min != null) return `${tilde}${money(fact.amount_min)}+`;
  if (fact.amount_max != null) return `up to ${money(fact.amount_max)}`;
  return "—";
}

const ORDINAL_EXCEPTIONS: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };

function ordinal(day: number): string {
  const teen = day % 100;
  if (teen >= 11 && teen <= 13) return `${day}th`;
  return `${day}${ORDINAL_EXCEPTIONS[day % 10] ?? "th"}`;
}

/** `the 5th`, `the 5th–10th`, `weekly`, or empty when we simply were not told. */
export function factTiming(fact: Fact): string {
  const cadence = fact.frequency === "monthly" ? "" : fact.frequency.replace("_", "-");
  if (fact.day != null) return `${ordinal(fact.day)}${cadence ? ` · ${cadence}` : ""}`;
  if (fact.day_min != null && fact.day_max != null) {
    return `${ordinal(fact.day_min)}–${ordinal(fact.day_max)}`;
  }
  return cadence || "";
}

export function shortDate(iso: string): string {
  const parsed = new Date(`${iso}T00:00:00`);
  return parsed.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function longDate(iso: string): string {
  const parsed = new Date(`${iso}T00:00:00`);
  return parsed.toLocaleDateString("en-IN", { day: "numeric", month: "long" });
}

/** `₹28.6k` — for calendar cells, where the full figure will not fit. */
export function compactMoney(amount: number): string {
  const sign = amount < 0 ? "-" : "";
  const value = Math.abs(amount);
  if (value >= 100000) return `${sign}₹${(value / 100000).toFixed(1)}L`;
  if (value >= 1000) {
    const thousands = value / 1000;
    return `${sign}₹${thousands >= 100 ? Math.round(thousands) : thousands.toFixed(1)}k`;
  }
  return `${sign}₹${Math.round(value)}`;
}
