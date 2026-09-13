"use client";

import { useState } from "react";
import {
  factAmount,
  factTiming,
  factsOfKind,
  groupTotal,
  money,
  type FactKind,
  type FinanceSnapshot,
} from "@/lib/finance";
import styles from "./ledger.module.css";

/**
 * Everything Kubera has been told, as one continuous ledger.
 *
 * Not cards. A row per group, hairline-separated, flush to the panel edge —
 * and exactly one of them opened at a time, the one the conversation is on.
 * Border, fill and weight are spent on that single row, which is what gives
 * the rail a focus; nine equally-boxed sections have none.
 *
 * Every figure on screen came from the server. `groupTotal` reads the
 * subtotals the agent computed with the same `planning_amount` the planner
 * uses, so the rail can never show a friendlier number than the plan.
 */

/** The order Kubera asks in, and the order they read down the rail. */
const ORDER: FactKind[] = ["balance", "income", "essential", "debt", "optional"];

const TITLES: Record<FactKind, string> = {
  balance: "In hand",
  income: "Coming in",
  essential: "Essentials",
  debt: "Loans & card",
  optional: "Could wait",
};

/** Shown in the amount column before the group has anything in it. */
const WAITING: Record<FactKind, string> = {
  balance: "not yet",
  income: "not yet",
  essential: "not yet",
  debt: "not yet",
  optional: "not yet",
};

/** What a fact looks like right now, for spotting the one that just changed. */
function signatures(snapshot: FinanceSnapshot): Map<string, string> {
  return new Map(
    snapshot.facts.map((fact) => [
      fact.id,
      `${fact.kind}:${fact.amount}:${fact.amount_min}:${fact.amount_max}:${fact.day}:${fact.status}`,
    ]),
  );
}

/**
 * Which group the user just spoke about.
 *
 * Derived by diffing consecutive snapshots rather than asked for from the
 * server: the agent records facts, it does not narrate which part of the
 * screen it is on, and inventing a field for that would put the model in
 * charge of the UI's focus. If nothing has changed yet — the first render, or
 * a version bump that only carried a name — it falls back to the next group
 * still waiting for an answer, which is what Kubera is about to ask about.
 *
 * Adjusted during render rather than in an effect, so the lit row and the
 * figure that lit it paint in the same frame.
 */
function useActiveKind(snapshot: FinanceSnapshot): FactKind | null {
  const [seen, setSeen] = useState(() => ({
    version: snapshot.version,
    facts: signatures(snapshot),
  }));
  const [active, setActive] = useState<FactKind | null>(null);

  if (seen.version !== snapshot.version) {
    const now = signatures(snapshot);
    let changed: FactKind | null = null;
    for (const [id, signature] of now) {
      if (seen.facts.get(id) !== signature) {
        changed = snapshot.facts.find((fact) => fact.id === id)?.kind ?? null;
        break;
      }
    }
    setSeen({ version: snapshot.version, facts: now });
    if (changed) setActive(changed);
  }

  if (active) return active;
  // Before the call is live there is no conversation to be "on", and lighting
  // a row then promises a question nobody is about to ask.
  if (snapshot.version < 0) return null;
  return ORDER.find((kind) => factsOfKind(snapshot, kind).length === 0) ?? null;
}

export function LedgerRail({ snapshot }: { snapshot: FinanceSnapshot }) {
  const active = useActiveKind(snapshot);
  const plan = snapshot.plan ?? snapshot.projection;
  const started = snapshot.version >= 0;

  const cut = new Set(
    snapshot.plan?.cut.map((movement) => movement.fact_id) ?? [],
  );
  const minimums = new Set(
    snapshot.plan?.actions
      .filter((action) => action.kind === "pay_minimum")
      .map((action) => action.fact_id) ?? [],
  );

  return (
    <div className={styles.rail}>
      <div className={styles.head}>
        <h2 className={styles.headTitle}>
          {snapshot.name ? `${snapshot.name}’s month` : "What I have so far"}
        </h2>
        {snapshot.facts.length > 0 ? (
          <span className={`num ${styles.headCount}`}>
            {snapshot.facts.length}
          </span>
        ) : null}
      </div>

      <div className={styles.rows}>
        {ORDER.map((kind) => {
          const facts = factsOfKind(snapshot, kind);
          const total = groupTotal(snapshot, kind);
          const open = active === kind && facts.length > 0;
          const isActive = active === kind;

          return (
            <div key={kind}>
              <div
                className={[
                  styles.row,
                  isActive ? styles.rowActive : "",
                  facts.length === 0 ? styles.rowWaiting : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span className={styles.rowName}>{TITLES[kind]}</span>
                {total.amount == null ? (
                  <span className={styles.rowWait}>
                    {isActive ? "asking now" : WAITING[kind]}
                  </span>
                ) : (
                  <span
                    className={[
                      "num",
                      styles.rowAmount,
                      kind === "income" ? styles.amountIn : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    {total.estimated ? "~" : ""}
                    {money(total.amount)}
                  </span>
                )}
              </div>

              {open ? (
                <div className={styles.detail}>
                  {facts.map((fact) => {
                    const when = factTiming(fact);
                    const held = cut.has(fact.id);
                    const paid = fact.status === "already_paid";
                    return (
                      <div
                        key={fact.id}
                        className={[
                          styles.item,
                          fact.certainty === "estimated" ? styles.itemSoft : "",
                          held || paid ? styles.itemStruck : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <span className={styles.itemName}>
                          {fact.label}
                          {when ? <em>{when}</em> : null}
                          {paid ? <em>paid</em> : null}
                          {held ? <em>on hold</em> : null}
                          {minimums.has(fact.id) && fact.minimum_due != null ? (
                            <em>min {money(fact.minimum_due)}</em>
                          ) : null}
                        </span>
                        <span className={`num ${styles.itemAmount}`}>
                          {factAmount(fact)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className={styles.standing}>
        <h3 className={styles.standingTitle}>Lowest you go</h3>
        {plan ? (
          <>
            <p
              className={[
                "num",
                styles.standingFigure,
                plan.min_balance < 0 ? styles.figureLow : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {money(plan.min_balance)}
            </p>
            <p className={styles.standingNote}>
              {plan.solvable
                ? "The tightest point in the next thirty days."
                : `Short by ${money(plan.shortfall)} before the month is out.`}
            </p>
          </>
        ) : (
          <>
            <p className={`num ${styles.standingFigure} ${styles.figureIdle}`}>
              —
            </p>
            <p className={styles.standingNote}>
              {started
                ? "Appears once I know what you have on hand."
                : "Appears once the call starts."}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
