"use client";

import { compactMoney, type DayCell, type Movement, type Plan } from "@/lib/finance";
import styles from "./plan.module.css";

/**
 * The thirty days, on a real weekday grid.
 *
 * Only days where money actually moves carry any ink. Most of the month is
 * silent, and that silence is the information — a quiet fortnight followed by
 * a hard week is the shape people need to see. Tinting every cell by balance
 * spends the colour everywhere and leaves nothing to point with.
 */

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

type Tone = "quiet" | "out" | "in" | "low" | "today";

/**
 * Spending the planner spread evenly across the window rather than landing on
 * a day — an undated "about five thousand eating out" becomes ~₹166 on all
 * thirty days (see `plan._occurrences`).
 *
 * Drawn in every cell it turns the calendar back into the wall of noise this
 * design exists to get rid of, and it is not a date the user needs to know.
 * So it is lifted out and stated once underneath, where it is still honest
 * about being part of the month.
 */
function ambientIds(plan: Plan): Set<string> {
  const seen = new Map<string, number>();
  for (const cell of plan.timeline) {
    for (const movement of cell.movements) {
      seen.set(movement.fact_id, (seen.get(movement.fact_id) ?? 0) + 1);
    }
  }
  const threshold = Math.max(2, Math.round(plan.timeline.length / 3));
  return new Set(
    [...seen.entries()]
      .filter(([, days]) => days >= threshold)
      .map(([id]) => id),
  );
}

/** What each spread-out cost adds up to over the window. */
function ambientTotals(plan: Plan, ids: Set<string>): Movement[] {
  const totals = new Map<string, Movement>();
  for (const cell of plan.timeline) {
    for (const movement of cell.movements) {
      if (!ids.has(movement.fact_id)) continue;
      const running = totals.get(movement.fact_id);
      totals.set(
        movement.fact_id,
        running
          ? { ...running, amount: running.amount + movement.amount }
          : { ...movement },
      );
    }
  }
  return [...totals.values()];
}

/** The one movement worth naming in a cell: the biggest that actually lands. */
function headline(movements: Movement[]): Movement | null {
  if (!movements.length) return null;
  return movements.reduce((biggest, movement) =>
    movement.amount > biggest.amount ? movement : biggest,
  );
}

function toneFor(
  cell: DayCell,
  lowestDay: string,
  isToday: boolean,
  landed: Movement[],
): Tone {
  if (cell.day === lowestDay) return "low";
  if (isToday) return "today";
  // Tone follows what actually lands on the day, not the daily slice of a
  // monthly average — otherwise every cell in the month is tinted.
  if (!landed.length) return "quiet";
  if (landed.some((movement) => movement.kind === "income")) return "in";
  return "out";
}

/**
 * Note there is no "held" state here. When the planner puts something on hold
 * it rebuilds the timeline with that fact skipped (`_build_timeline(skip=...)`),
 * so a cut expense is simply not in the days any more. Where it went is said
 * once, in "What to change".
 */
export function MonthCalendar({ plan }: { plan: Plan }) {
  if (!plan.timeline.length) return null;

  const lowest = plan.timeline.reduce((low, cell) =>
    cell.balance < low.balance ? cell : low,
  );
  const firstDay = new Date(`${plan.timeline[0].day}T00:00:00`).getDay();
  const ambient = ambientIds(plan);
  const spread = ambientTotals(plan, ambient);

  return (
    <div className={styles.cal}>
      <div className={styles.calHead}>
        {WEEKDAYS.map((letter, index) => (
          <span key={index} className={styles.weekday}>
            {letter}
          </span>
        ))}
      </div>

      <div className={styles.calBody}>
        {/* The window starts on whatever weekday today happens to be, so the
            grid needs leading blanks or every column would be a lie. */}
        {Array.from({ length: firstDay }, (_, index) => (
          <span key={`pad-${index}`} className={styles.pad} aria-hidden />
        ))}

        {plan.timeline.map((cell) => {
          const date = new Date(`${cell.day}T00:00:00`);
          const dayNumber = date.getDate();
          const isToday = cell.index === 0;
          const landed = cell.movements.filter(
            (movement) => !ambient.has(movement.fact_id),
          );
          const tone = toneFor(cell, lowest.day, isToday, landed);
          const lead = headline(landed);

          return (
            <div
              key={cell.day}
              className={[styles.cell, styles[`tone_${tone}`]]
                .filter(Boolean)
                .join(" ")}
            >
              <span className={styles.cellNum}>
                <span className="num">{dayNumber}</span>
                {dayNumber === 1 ? (
                  <em className={styles.cellMonth}>
                    {date.toLocaleDateString("en-IN", { month: "short" })}
                  </em>
                ) : null}
              </span>

              {lead ? (
                <span className={styles.cellMove}>
                  <span className={styles.cellLabel}>{lead.label}</span>
                  <span className={`num ${styles.cellAmount}`}>
                    {lead.kind === "income" ? "+" : ""}
                    {compactMoney(lead.amount)}
                  </span>
                </span>
              ) : null}

              {landed.length > 1 ? (
                <span className={styles.cellMore}>+{landed.length - 1} more</span>
              ) : null}

              {isToday ? <span className={styles.cellFlag}>today</span> : null}
              {cell.day === lowest.day ? (
                <span className={styles.cellFlag}>
                  lowest · <span className="num">{compactMoney(cell.balance)}</span>
                </span>
              ) : null}
            </div>
          );
        })}
      </div>

      {spread.length ? (
        <p className={styles.spread}>
          Also across the month:{" "}
          {spread.map((movement, index) => (
            <span key={movement.fact_id}>
              {index > 0 ? ", " : ""}
              {movement.label}{" "}
              <b className="num">
                {movement.certainty === "estimated" ? "~" : ""}
                {compactMoney(movement.amount)}
              </b>
            </span>
          ))}
          .
        </p>
      ) : null}
    </div>
  );
}
