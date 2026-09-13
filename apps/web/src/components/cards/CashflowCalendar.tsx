"use client";

import { useMemo, useState } from "react";
import {
  compactMoney,
  longDate,
  money,
  type DayCell,
  type Plan,
} from "@/lib/finance";
import { Card } from "./Card";
import styles from "./cards.module.css";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

type CashflowCalendarProps = {
  plan: Plan;
  /** True once the user has asked for a plan — the cuts below are then real advice. */
  planned: boolean;
};

type Tint = { className: string; alpha: number };

/**
 * How full a day looks.
 *
 * Scaled against the highest balance in the window rather than against a fixed
 * rupee threshold: ₹5,000 left is comfortable for one person and desperate for
 * another, and the calendar should not pretend to know which.
 */
function tintFor(balance: number, peak: number): Tint {
  if (balance < 0) return { className: styles.dayNegative, alpha: 1 };
  if (peak <= 0) return { className: styles.dayFlat, alpha: 0 };
  return { className: styles.dayPositive, alpha: Math.min(balance / peak, 1) };
}

function weekdayOf(iso: string): number {
  return new Date(`${iso}T00:00:00`).getDay();
}

function dayOfMonth(iso: string): number {
  return Number(iso.slice(8, 10));
}

function monthLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
    month: "short",
  });
}

export function CashflowCalendar({ plan, planned }: CashflowCalendarProps) {
  const [selected, setSelected] = useState<string | null>(null);

  const { cells, leading, peak } = useMemo(() => {
    const timeline = plan.timeline;
    return {
      cells: timeline,
      // The window starts today, not on the 1st, so the grid needs blanks to
      // put day one under the right weekday.
      leading: timeline.length ? weekdayOf(timeline[0].day) : 0,
      peak: timeline.reduce((high, cell) => Math.max(high, cell.balance), 0),
    };
  }, [plan.timeline]);

  if (!cells.length) return null;

  const crunch = plan.crunch_day;
  // Opens on the tightest day rather than on nothing. In a month that works
  // there is no crunch day to fall back on, and the detail panel — the part
  // that says *why* a day is tight — would never appear unless the user
  // happened to click.
  const lowest = cells.reduce((worst, cell) =>
    cell.balance < worst.balance ? cell : worst,
  );
  const chosen: DayCell =
    cells.find((cell) => cell.day === selected) ?? lowest;

  const signature = cells.map((cell) => cell.balance).join(",");
  const tone = plan.solvable ? "plain" : "bad";

  return (
    <Card
      title="The next 30 days"
      signature={signature}
      tone={tone}
      note={`${longDate(cells[0].day)} – ${longDate(cells[cells.length - 1].day)}`}
    >
      <div className={styles.weekdays} aria-hidden="true">
        {WEEKDAYS.map((letter, index) => (
          <span key={`${letter}-${index}`}>{letter}</span>
        ))}
      </div>

      <div className={styles.calendar} role="grid" aria-label="Daily balance">
        {Array.from({ length: leading }, (_, index) => (
          <span key={`blank-${index}`} className={styles.dayBlank} aria-hidden="true" />
        ))}

        {cells.map((cell) => {
          const tint = tintFor(cell.balance, peak);
          const startsMonth = dayOfMonth(cell.day) === 1;
          const isCrunch = crunch === cell.day || cell.day === lowest.day;
          const isChosen = chosen?.day === cell.day;
          return (
            <button
              key={cell.day}
              type="button"
              role="gridcell"
              onClick={() => setSelected(cell.day)}
              style={{ "--fill": tint.alpha } as React.CSSProperties}
              className={[
                styles.day,
                tint.className,
                startsMonth ? styles.dayNewMonth : "",
                isCrunch ? styles.dayCrunch : "",
                isChosen ? styles.daySelected : "",
              ]
                .filter(Boolean)
                .join(" ")}
              aria-label={`${longDate(cell.day)}: ${money(cell.balance)}${
                isCrunch ? ", tightest day" : ""
              }`}
            >
              <span className={styles.dayNumber}>
                {startsMonth ? monthLabel(cell.day) : dayOfMonth(cell.day)}
              </span>
              <span className={styles.dayBalance}>{compactMoney(cell.balance)}</span>
              {cell.movements.length ? (
                <span className={styles.dayDots} aria-hidden="true">
                  {cell.in > 0 ? <i className={styles.dotIn} /> : null}
                  {cell.out > 0 ? <i className={styles.dotOut} /> : null}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <DayDetail
        cell={chosen}
        isCrunch={chosen.day === crunch}
        isLowest={chosen.day === lowest.day}
      />

      {planned && plan.cut.length ? (
        <p className={styles.calendarFootnote}>
          Already assumes holding off on{" "}
          {plan.cut.map((movement) => movement.label).join(", ")}.
        </p>
      ) : null}
    </Card>
  );
}

function DayDetail({
  cell,
  isCrunch,
  isLowest,
}: {
  cell: DayCell;
  isCrunch: boolean;
  isLowest: boolean;
}) {
  const tag = isCrunch ? "Short here" : isLowest ? "Tightest day" : null;
  return (
    <div className={styles.dayDetail}>
      <div className={styles.dayDetailHead}>
        <strong>{longDate(cell.day)}</strong>
        <span className={isCrunch ? styles.crunchTag : styles.dayDetailBalance}>
          {tag ? `${tag} · ` : ""}
          {money(cell.balance)}
        </span>
      </div>
      {cell.movements.length ? (
        <ul className={styles.movementList}>
          {cell.movements.map((movement, index) => (
            <li key={`${movement.fact_id}-${index}`}>
              <span>{movement.label}</span>
              <span
                className={
                  movement.kind === "income" ? styles.amountIn : styles.amountOut
                }
              >
                {movement.kind === "income" ? "+" : "−"}
                {money(movement.amount)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.dayDetailEmpty}>Nothing moves today.</p>
      )}
    </div>
  );
}
