"use client";

import { money, type Conflict } from "@/lib/finance";
import { Card } from "./Card";
import styles from "./cards.module.css";

/**
 * Figures the user restated as something materially different. The newer value
 * is the one being used — a correction is far more common than a contradiction
 * — but both stay on screen so it is obvious what changed and what to confirm.
 */
export function ConflictCard({ conflicts }: { conflicts: Conflict[] }) {
  if (!conflicts.length) return null;

  return (
    <Card
      title="Worth confirming"
      signature={conflicts.map((c) => `${c.fact_id}:${c.current}`).join("|")}
      tone="warn"
    >
      <ul className={styles.conflicts}>
        {conflicts.map((conflict) => (
          <li key={conflict.fact_id}>
            <span className={styles.ledgerLabel}>{conflict.label}</span>
            <span className={styles.wasNow}>
              <s>{money(conflict.previous)}</s>
              <span aria-hidden="true">→</span>
              <strong>{money(conflict.current)}</strong>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
