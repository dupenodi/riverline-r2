"use client";

import { useEffect, useRef, useState } from "react";
import {
  entryAmount,
  formatDay,
  money,
  type FinanceEntry,
  type FinanceKind,
  type TransactionsState,
} from "@/lib/transactions";
import styles from "./rail.module.css";

const KIND_LABEL: Record<FinanceKind, string> = {
  income: "In",
  owed: "Owed",
  need: "Needs",
  debt: "Debts",
  flex: "Flex",
};

type MoneyRailProps = {
  state: TransactionsState;
};

export function MoneyRail({ state }: MoneyRailProps) {
  const prev = useRef(state);
  const [pulse, setPulse] = useState<string | null>(null);

  useEffect(() => {
    const keys = changedGroups(prev.current, state);
    prev.current = state;
    if (keys.length === 0) return;
    setPulse(keys[0]);
    const timer = window.setTimeout(() => setPulse(null), 1200);
    return () => window.clearTimeout(timer);
  }, [state]);

  const groups = KIND_LABEL;
  const byKind = (kind: FinanceKind) =>
    state.entries.filter((entry) => entry.kind === kind);
  const advice = state.advice;
  const hasAdvice =
    (advice?.points.length ?? 0) > 0 || advice?.payoff != null;
  const hasNow = state.cash != null || state.derived != null;
  const hasOpen = state.missing.length > 0 || state.conflicts.length > 0;
  const hasLists = state.entries.length > 0;
  if (!hasNow && !hasLists && !hasOpen && !hasAdvice) return null;

  return (
    <aside className={styles.rail} aria-label="Money summary">
      {hasNow ? (
        <section
          className={styles.group}
          data-pulse={pulse === "now" ? "true" : undefined}
        >
          <h2 className={styles.heading}>Now</h2>
          {state.cash != null ? (
            <p className={styles.row}>
              <span>In hand</span>
              <span data-num>{money(state.cash)}</span>
            </p>
          ) : null}
          {state.derived ? (
            <>
              <p className={styles.row}>
                <span>After 30 days</span>
                <span data-num data-tone={tone(state.derived.finish)}>
                  {signed(state.derived.finish)}
                </span>
              </p>
              <p className={styles.row} data-crunch={state.derived.crunch.amount < 0 ? "true" : undefined}>
                <span>Lowest {formatDay(state.derived.crunch.date)}</span>
                <span data-num data-tone={tone(state.derived.crunch.amount)}>
                  {signed(state.derived.crunch.amount)}
                </span>
              </p>
            </>
          ) : null}
        </section>
      ) : null}

      {(Object.keys(groups) as FinanceKind[]).map((kind) => {
        const rows = byKind(kind);
        if (rows.length === 0) return null;
        return (
          <section
            key={kind}
            className={styles.group}
            data-pulse={pulse === kind ? "true" : undefined}
          >
            <h2 className={styles.heading}>{groups[kind]}</h2>
            {rows.map((entry) => (
              <p key={entry.id} className={styles.row}>
                <span>
                  {entry.label}
                  {entry.status === "paid" ? " · paid" : ""}
                  {when(entry)}
                </span>
                <span data-num>{entryAmount(entry)}</span>
              </p>
            ))}
          </section>
        );
      })}

      {hasOpen ? (
        <section
          className={styles.group}
          data-pulse={pulse === "open" ? "true" : undefined}
        >
          <h2 className={styles.heading}>Open</h2>
          {state.conflicts.map((line) => (
            <p key={line} className={styles.note} data-warn>
              {line}
            </p>
          ))}
          {state.missing.map((line) => (
            <p key={line} className={styles.note}>
              Still need {line === "available" ? "money in hand" : line}
            </p>
          ))}
        </section>
      ) : null}

      {hasAdvice && advice ? (
        <section
          className={styles.group}
          data-pulse={pulse === "advice" ? "true" : undefined}
        >
          <h2 className={styles.heading}>Advice</h2>
          {advice.points.length > 0 ? (
            <ul className={styles.adviceList}>
              {advice.points.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
          <p
            className={styles.payoff}
            data-ok={advice.payoff.ok ? "true" : "false"}
          >
            <span className={styles.payoffLabel}>Payoff</span>
            <span className={styles.payoffBody}>
              Lowest{" "}
              <span data-num data-tone={tone(advice.payoff.lowest)}>
                {signed(advice.payoff.lowest)}
              </span>{" "}
              on {formatDay(advice.payoff.date)}.{" "}
              {advice.payoff.ok
                ? "You stay above zero."
                : "There is still a hole."}
            </span>
          </p>
        </section>
      ) : null}
    </aside>
  );
}

function when(entry: FinanceEntry): string {
  if (entry.cadence === "daily") return " · every day";
  if (entry.cadence === "weekly") return " · weekly";
  if (entry.on_date) return ` · ${formatDay(entry.on_date)}`;
  if (entry.day != null) return ` · ${entry.day}`;
  return "";
}

function signed(amount: number): string {
  if (amount > 0) return `+${money(amount)}`;
  if (amount < 0) return `−${money(Math.abs(amount))}`;
  return money(0);
}

function tone(amount: number): "in" | "out" | undefined {
  if (amount > 0) return "in";
  if (amount < 0) return "out";
  return undefined;
}

function changedGroups(
  prev: TransactionsState,
  next: TransactionsState,
): string[] {
  if (prev.version === next.version) return [];
  const keys: string[] = [];
  if (
    prev.cash !== next.cash ||
    prev.derived?.finish !== next.derived?.finish ||
    prev.derived?.crunch.amount !== next.derived?.crunch.amount
  ) {
    keys.push("now");
  }
  for (const kind of ["income", "owed", "need", "debt", "flex"] as FinanceKind[]) {
    const a = prev.entries.filter((e) => e.kind === kind).map(stamp).join();
    const b = next.entries.filter((e) => e.kind === kind).map(stamp).join();
    if (a !== b) keys.push(kind);
  }
  if (
    prev.missing.join() !== next.missing.join() ||
    prev.conflicts.join() !== next.conflicts.join()
  ) {
    keys.push("open");
  }
  if (JSON.stringify(prev.advice) !== JSON.stringify(next.advice)) {
    keys.push("advice");
  }
  return keys;
}

function stamp(entry: FinanceEntry): string {
  return `${entry.id}:${entry.amount}:${entry.day}:${entry.status}`;
}
