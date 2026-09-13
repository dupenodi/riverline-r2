"use client";

import { longDate, money, type FinanceSnapshot, type Plan } from "@/lib/finance";
import { MonthCalendar } from "./MonthCalendar";
import styles from "./plan.module.css";

/**
 * The finished plan: the verdict in a sentence, four figures, the month, and
 * the things to change.
 *
 * This only ever renders once the user has confirmed their details and Kubera
 * has actually built a plan. Until then the rail is the whole picture — the
 * assignment wants cards updating live, and it wants a plan at the end; those
 * are two different moments and conflating them is what made the old screen
 * feel like a dashboard of unfinished thoughts.
 *
 * Every sentence about money here is the planner's, read out rather than
 * recomposed. Nothing on this screen is computed in the browser.
 */

/** Spelled out: "2 things on hold" reads like a receipt, not a sentence. */
const COUNTS: Record<number, string> = {
  2: "Two",
  3: "Three",
  4: "Four",
  5: "Five",
  6: "Six",
};

const MARKS: Record<string, string> = {
  cut_optional: "hold",
  pay_minimum: "min",
  shortfall: "gap",
  pay: "pay",
};

function verdict(plan: Plan): { head: string; sub: string } {
  if (!plan.solvable) {
    return {
      head: "This month doesn’t balance.",
      sub: "Even with everything optional already gone and the card at its minimum, there is nothing left to move.",
    };
  }
  const held = plan.cut.length;
  if (held === 0) {
    return {
      head: "The month works as it stands.",
      sub: "Everything due gets paid on the day it is due, without changing anything.",
    };
  }
  return {
    head:
      held === 1
        ? "One thing on hold, and the month works."
        : `${COUNTS[held] ?? held} things on hold, and the month works.`,
    sub: "Everything due gets paid on the day it is due. It leaves very little spare, so an unexpected bill would break it.",
  };
}

export function PlanView({ snapshot }: { snapshot: FinanceSnapshot }) {
  const plan = snapshot.plan;
  if (!plan) return null;

  const { head, sub } = verdict(plan);
  // The per-day "pay X on the 20th" actions are already drawn on the calendar;
  // repeating them as a list underneath it says the same thing twice.
  const changes = plan.actions.filter((action) => action.kind !== "pay");

  return (
    <div className={styles.plan}>
      <div className={styles.verdict}>
        <div className={styles.verdictText}>
          <h2 className={styles.head}>{head}</h2>
          <p className={styles.sub}>{sub}</p>
        </div>

        <dl className={styles.figures}>
          <div>
            <dt>In hand</dt>
            <dd className="num">{money(plan.opening_balance)}</dd>
          </div>
          <div>
            <dt>Coming in</dt>
            <dd className={`num ${styles.figIn}`}>{money(plan.total_in)}</dd>
          </div>
          <div>
            <dt>Going out</dt>
            <dd className="num">{money(plan.total_out)}</dd>
          </div>
          <div>
            <dt>{plan.solvable ? "Lowest" : "Short by"}</dt>
            <dd className={`num ${styles.figLow}`}>
              {money(plan.solvable ? plan.min_balance : plan.shortfall)}
            </dd>
          </div>
        </dl>
      </div>

      <div className={styles.calScroll}>
        <MonthCalendar plan={plan} />
      </div>

      {changes.length ? (
        <div className={styles.changes}>
          <h3 className={styles.changesHead}>What to change</h3>
          {changes.map((action, index) => (
            <div key={`${action.kind}-${action.fact_id}-${index}`} className={styles.change}>
              <span
                className={[
                  styles.mark,
                  action.kind === "pay_minimum" ? styles.markMin : "",
                  action.kind === "shortfall" ? styles.markGap : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {MARKS[action.kind] ?? "do"}
              </span>
              {/* No amount column. `action.amount` is the money *freed* by the
                  change, not the payment: for a card minimum it is 16,200 —
                  the difference — sitting next to the words "pay the minimum",
                  which reads as the amount to pay and is wrong by an order of
                  magnitude. The planner's own detail line already carries the
                  right figure, and it is the tested wording. */}
              <span className={styles.changeText}>
                {action.label}
                {action.detail ? <em>{action.detail}</em> : null}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {!plan.solvable ? (
        <p className={styles.gap}>
          The gap is <b className="num">{money(plan.shortfall)}</b>
          {plan.crunch_day ? (
            <>
              , and it opens on <b>{longDate(plan.crunch_day)}</b>
            </>
          ) : null}
          . Closing it needs money from outside this plan, or a payment moved by
          agreement with whoever is owed. I can’t arrange either of those.
        </p>
      ) : null}
    </div>
  );
}
