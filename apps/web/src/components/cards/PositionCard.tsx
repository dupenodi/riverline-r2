"use client";

import { longDate, money, type Plan } from "@/lib/finance";
import { Card } from "./Card";
import styles from "./cards.module.css";

type PositionCardProps = {
  plan: Plan;
  /** False while this is still a forecast rather than an agreed plan. */
  planned: boolean;
};

/**
 * The headline: how the month ends, and — the part a monthly total hides —
 * whether it dips below zero on the way there.
 */
export function PositionCard({ plan, planned }: PositionCardProps) {
  const closing = plan.timeline.length
    ? plan.timeline[plan.timeline.length - 1].balance
    : plan.opening_balance;

  const tone = !plan.solvable ? "bad" : plan.min_balance < plan.total_in * 0.05 ? "warn" : "good";

  return (
    <Card
      title={planned ? "Your 30-day plan" : "Where this is heading"}
      signature={`${closing}:${plan.min_balance}:${plan.solvable}`}
      tone={tone}
      note={planned ? undefined : "so far"}
    >
      <p className={styles.heroFigure}>{money(closing)}</p>
      <p className={styles.heroCaption}>
        {plan.solvable
          ? "left at the end of the window"
          : `short by ${money(plan.shortfall)} before the end`}
      </p>

      <dl className={styles.statRow}>
        <div>
          <dt>In hand today</dt>
          <dd>{money(plan.opening_balance)}</dd>
        </div>
        <div>
          <dt>Coming in</dt>
          <dd className={styles.amountIn}>+{money(plan.total_in)}</dd>
        </div>
        <div>
          <dt>Going out</dt>
          <dd className={styles.amountOut}>−{money(plan.total_out)}</dd>
        </div>
      </dl>

      <p className={plan.solvable ? styles.lowPoint : styles.lowPointBad}>
        {plan.solvable ? "Tightest point" : "Lowest point"}:{" "}
        <strong>{money(plan.min_balance)}</strong>
        {plan.crunch_day ? ` on ${longDate(plan.crunch_day)}` : null}
      </p>
    </Card>
  );
}
