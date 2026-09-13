"use client";

import {
  factAmount,
  factTiming,
  money,
  type Fact,
  type FactKind,
} from "@/lib/finance";
import { Card } from "./Card";
import styles from "./cards.module.css";

const TITLES: Record<FactKind, string> = {
  balance: "Money in hand",
  income: "Coming in",
  essential: "Essentials",
  debt: "Debts",
  optional: "Could be cut",
};

type LedgerCardProps = {
  kind: FactKind;
  facts: Fact[];
  /** Ids the plan has proposed holding off on, so the row can say so. */
  cutIds?: Set<string>;
  /** Ids the plan has dropped to the minimum payment. */
  minimumIds?: Set<string>;
};

/**
 * One kind of fact, as a list. Each card appears only once it has something in
 * it — the screen fills up as the user talks instead of greeting them with a
 * wall of empty boxes.
 */
export function LedgerCard({
  kind,
  facts,
  cutIds,
  minimumIds,
}: LedgerCardProps) {
  if (!facts.length) return null;

  // One balance under a card already titled "Money in hand" printed the same
  // words twice. It is the one figure worth reading at a glance anyway.
  if (kind === "balance" && facts.length === 1) {
    const only = facts[0];
    return (
      <Card title={TITLES[kind]} signature={`${only.id}:${only.amount}`}>
        <p className={styles.balanceFigure}>{factAmount(only)}</p>
      </Card>
    );
  }

  const total = facts.reduce((sum, fact) => sum + (fact.amount ?? fact.amount_min ?? 0), 0);
  const anyEstimated = facts.some((fact) => fact.certainty === "estimated");
  const signature = facts
    .map((fact) => `${fact.id}:${fact.amount}:${fact.day}:${fact.status}`)
    .join("|");

  return (
    <Card
      title={TITLES[kind]}
      signature={signature}
      note={facts.length > 1 ? `${anyEstimated ? "~" : ""}${money(total)}` : undefined}
    >
      <ul className={styles.ledger}>
        {facts.map((fact) => {
          const timing = factTiming(fact);
          const paid = fact.status === "already_paid";
          const cut = cutIds?.has(fact.id);
          const minimum = minimumIds?.has(fact.id);
          return (
            <li
              key={fact.id}
              className={[
                styles.ledgerRow,
                fact.certainty === "estimated" ? styles.estimated : "",
                paid || cut ? styles.struck : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span className={styles.ledgerLabel}>
                {fact.label}
                {timing ? <em className={styles.ledgerWhen}>{timing}</em> : null}
              </span>
              <span className={styles.ledgerAmount}>{factAmount(fact)}</span>
              {paid ? <span className={styles.tag}>paid</span> : null}
              {cut ? <span className={styles.tagWarn}>on hold</span> : null}
              {minimum && fact.minimum_due != null ? (
                <span className={styles.tagWarn}>min {money(fact.minimum_due)}</span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
