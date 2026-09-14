/**
 * Money list the agent pushes over RTVI after every add/remove.
 */

export type MoneyDirection = "incoming" | "outgoing";

export type MoneyItem = {
  id: string;
  direction: MoneyDirection;
  label: string;
  amount: number;
  /** Day of month (1–31) when this lands. */
  day: number;
};

export type TransactionsState = {
  type: "transactions";
  version: number;
  name: string | null;
  items: MoneyItem[];
};

export const EMPTY_TRANSACTIONS: TransactionsState = {
  type: "transactions",
  version: 0,
  name: null,
  items: [],
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

function isState(value: unknown): value is TransactionsState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<TransactionsState>;
  return (
    candidate.type === "transactions" &&
    typeof candidate.version === "number" &&
    Array.isArray(candidate.items)
  );
}

export function acceptTransactions(
  current: TransactionsState,
  incoming: unknown,
): TransactionsState {
  if (!isState(incoming)) return current;
  if (incoming.version < current.version) return current;
  return {
    type: "transactions",
    version: incoming.version,
    name: typeof incoming.name === "string" ? incoming.name : null,
    items: incoming.items.filter(isItem),
  };
}

export function money(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
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
