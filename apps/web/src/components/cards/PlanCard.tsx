"use client";

import { money, type Plan, type PlanAction } from "@/lib/finance";
import { Card } from "./Card";
import styles from "./cards.module.css";

const MARKS: Record<PlanAction["kind"], string> = {
  pay: "→",
  cut_optional: "✕",
  pay_minimum: "↓",
  shortfall: "!",
};

/**
 * The actions, in order — or, when the month genuinely does not balance, a
 * plain statement of the gap. There is no action for borrowing anywhere in the
 * planner's vocabulary, so there is nothing to render here for one.
 */
export function PlanCard({ plan }: { plan: Plan }) {
  if (!plan.actions.length) return null;

  // The planner already writes the shortfall sentence, and it is the tested
  // one. Lifting it out of the list to sit as the header stops the same
  // paragraph appearing twice, and keeps every word about money server-side.
  const gap = plan.actions.find((action) => action.kind === "shortfall");
  const steps = plan.actions.filter((action) => action.kind !== "shortfall");

  return (
    <Card
      title={plan.solvable ? "What to do" : "This does not balance"}
      signature={plan.actions.map((a) => `${a.kind}:${a.label}:${a.amount}`).join("|")}
      tone={plan.solvable ? "good" : "bad"}
    >
      {gap ? <p className={styles.shortfallLine}>{gap.detail}</p> : null}

      <ol className={styles.actions}>
        {steps.map((action, index) => (
          <li
            key={`${action.kind}-${action.label}-${index}`}
            className={action.kind === "shortfall" ? styles.actionBad : undefined}
          >
            <span className={styles.actionMark} aria-hidden="true">
              {MARKS[action.kind]}
            </span>
            <span className={styles.actionBody}>
              <strong>{action.label}</strong>
              {action.detail ? <em>{action.detail}</em> : null}
            </span>
            {action.kind === "pay" && action.amount ? (
              <span className={styles.actionAmount}>{money(action.amount)}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </Card>
  );
}
